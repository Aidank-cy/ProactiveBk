#!/usr/bin/env python3
"""Convert only the three 1k samples into two deterministic Parquet tables."""
import collections
import hashlib
import json
import os
from pathlib import Path
import sys

import pyarrow as pa
import pyarrow.parquet as pq

from swe_format import signature
from wildchat_adapter import convert as wildchat_convert
from swe_chat_adapter import convert as swe_convert, count_user_turns, dumps, records, main_agent_model_candidates, resolve_trace_model
from trace_ids import trace_id as make_trace_id
from unified_schema import TRACE_SCHEMA, EVENT_SCHEMA

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(os.environ.get("UNIFIED_TRACE_OUTPUT_DIR", Path(__file__).resolve().parents[1]))
SAMPLES = ROOT / "OriginalDataset-filter-1k"
def manifest(path):
    return json.loads((path / "sample_manifest.json").read_text(encoding="utf-8"))


def arrow_fields(path):
    return {f.name: str(f.type) for f in pq.ParquetFile(path).schema_arrow}


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    swe = SAMPLES / "SWE-Chat-filter-1k"
    swe_manifest = manifest(swe)
    filtered_swe = ROOT / "OriginalDataset-filter" / "SWE-Chat-filter"
    if Path(swe_manifest.get("source_directory", "")).name != filtered_swe.name:
        raise ValueError("SWE-chat sample must originate from SWE-Chat-filter")
    filtered_manifest = filtered_swe / "filter_manifest.json"
    if hashlib.sha256(filtered_manifest.read_bytes()).hexdigest() != swe_manifest.get("filtered_source_manifest_sha256"):
        raise ValueError("SWE-chat sample does not match the filtered source manifest")
    if swe_manifest.get("sampling_unit") != "session_id":
        raise ValueError("SWE-chat sample must use sampling_unit=session_id")
    selected = swe_manifest["selected"]
    if len(selected) != 1000 or len({item["session_id"] for item in selected}) != len(selected):
        raise ValueError("SWE-chat manifest does not contain 1000 unique Session IDs")
    for sample_name in ("WildChat-1M-filter-1k", "WildChat-4.8M-filter-1k"):
        sample_manifest = manifest(SAMPLES / sample_name)
        source = ROOT / "OriginalDataset-filter" / sample_name.removesuffix("-1k")
        if Path(sample_manifest.get("source_directory", "")).name != source.name:
            raise ValueError(f"{sample_name} must originate from its filtered source")
        if sample_manifest.get("source_revision") != json.loads((source / "filter_manifest.json").read_text())["source_revision"]:
            raise ValueError(f"{sample_name} filtered source revision mismatch")
    logs = pq.read_table(swe / "session_logs.parquet").to_pylist()
    sessions = pq.read_table(swe / "sessions.parquet").to_pylist()
    log_by_id = collections.defaultdict(list)
    session_by_id = collections.defaultdict(list)
    for row in logs:log_by_id[row["session_id"]].append(row)
    for row in sessions:session_by_id[row["session_id"]].append(row)

    inspection={"sampling_pipeline":"OriginalDataset-filter-1k/sample_1k.py", "sample_directories":{},"wildchat_schemas":{},
                "swe_metadata_schemas":{},"swe_agent_counts":dict(collections.Counter(x.get("agent") for x in sessions)),
                "swe_raw_types_by_agent":{},"swe_raw_formats_by_agent":{},"metadata_mapping_ambiguities":[],
                "notes":["SWE main conversations.parquet is absent; transcripts and transcripts1 are parsed.",
                         "Compact and subagent transcripts are supplementary and not merged into main chronology.",
                         "Full-session summaries and outcome labels are excluded from event metadata."]}
    for name in ("WildChat-1M-filter-1k","WildChat-4.8M-filter-1k"):
        d=SAMPLES/name;inspection["wildchat_schemas"][name]=arrow_fields(d/"train.parquet")
    for name in ("sessions","session_logs"):
        inspection["swe_metadata_schemas"][name]=arrow_fields(swe/f"{name}.parquet")
    for d in (SAMPLES/"WildChat-1M-filter-1k",SAMPLES/"WildChat-4.8M-filter-1k",swe):
        inspection["sample_directories"][d.name]={"files":sum(1 for p in d.rglob("*") if p.is_file()),
                                                   "top_level":sorted(p.name for p in d.iterdir())}

    trace_writer=pq.ParquetWriter(HERE/"traces.parquet.tmp",TRACE_SCHEMA,compression="zstd")
    event_writer=pq.ParquetWriter(HERE/"events.parquet.tmp",EVENT_SCHEMA,compression="zstd")
    trace_buffer=[];event_buffer=[];source_counts=collections.Counter();event_counts=collections.Counter()
    types_by_agent=collections.defaultdict(collections.Counter);formats_by_agent=collections.defaultdict(collections.Counter);file_formats_by_agent=collections.defaultdict(collections.Counter)
    failures=[];unrecognized=collections.Counter();null_content=collections.Counter();transforms=collections.Counter();adapter_actions=collections.Counter()
    missing_timestamps=collections.Counter();missing_source_ids=collections.Counter()
    model_resolution=collections.Counter();model_disagreements=[]
    unmatched_calls=0;unmatched_results=0;early_result_ids=0
    unmatched_calls_by_format=collections.Counter();unmatched_results_by_format=collections.Counter();unmatched_result_examples=[]
    def flush():
        nonlocal trace_buffer,event_buffer
        if trace_buffer:
            trace_writer.write_table(pa.Table.from_pylist(trace_buffer,schema=TRACE_SCHEMA));trace_buffer=[]
        if event_buffer:
            event_writer.write_table(pa.Table.from_pylist(event_buffer,schema=EVENT_SCHEMA));event_buffer=[]
    def add(trace,events,source_format=None):
        nonlocal unmatched_calls,unmatched_results,early_result_ids
        source_counts[trace["source"]]+=1;event_counts[trace["source"]]+=len(events)
        trace_buffer.append(trace);event_buffer.extend(events)
        trace_calls=set();trace_results=set();early_results=set()
        last_raw=None;last_block=None
        for e in events:
            if e["content"] is None or e["content"]=="":null_content[trace["source"]]+=1
            if e["timestamp"] is None:missing_timestamps[trace["source"]]+=1
            if e["source_event_id"] is None:missing_source_ids[trace["source"]]+=1
            m=json.loads(e["metadata"])
            raw=m.get("raw_record_index");block=m.get("block_index",m.get("part_index"))
            if raw is not None:
                if last_raw is not None and raw<last_raw:raise ValueError(f"raw record order reversed: {trace['trace_id']}")
                if last_raw==raw and block is not None and last_block is not None and block<last_block:
                    raise ValueError(f"content block order reversed: {trace['trace_id']}")
                last_raw=raw;last_block=block
            call_id=m.get("tool_call_id") or m.get("call_id")
            if call_id and e["event_type"]=="tool_call":trace_calls.add(call_id)
            if call_id and e["event_type"]=="tool_result":
                trace_results.add(call_id)
                if call_id not in trace_calls:early_results.add(call_id)
            if m.get("discarded_auxiliary_prefix"):transforms["discarded_leading_auxiliary_prefixes"]+=1
            if m.get("unpaired_agent_message"):adapter_actions["codex_unpaired_agent_messages_as_assistant"]+=1
            if m.get("event_msg_reasoning"):adapter_actions["codex_event_reasoning_as_thinking"]+=1
            if m.get("execution_start"):adapter_actions["copilot_execution_starts_as_system_events"]+=1
            if m.get("stop_message"):adapter_actions["grok_stop_assistant_messages"]+=1
            if m.get("original_type")=="custom_message":adapter_actions["pi_custom_messages_as_system_events"]+=1
            if m.get("ambiguous_mixed_tool_feedback_text"):adapter_actions["mixed_tool_feedback_text_ambiguous"]+=1
            if m.get("structured_user_attachment"):adapter_actions["opencode_user_file_parts_as_messages"]+=1
            if m.get("unrecognized_or_supplementary") or m.get("unrecognized_block") or m.get("unrecognized_agent"):
                unrecognized[(trace["source"],m.get("original_type") or m.get("original_block_type") or "unknown")]+=1
        unmatched_calls+=len(trace_calls-trace_results)
        unmatched_results+=len(trace_results-trace_calls)
        if trace["source"]=="swe_chat":
            unmatched_calls_by_format[source_format or "unknown"]+=len(trace_calls-trace_results)
            unmatched_results_by_format[source_format or "unknown"]+=len(trace_results-trace_calls)
            for call_id in sorted(trace_results-trace_calls):
                if len(unmatched_result_examples)<10:
                    unmatched_result_examples.append({"source_id":trace["source_id"],"trace_id":trace["trace_id"],"tool_call_id":call_id,"format":source_format})
        early_result_ids+=len(early_results & trace_calls)
        if len(event_buffer)>=10000 or len(trace_buffer)>=100:flush()
    try:
        for name,source in (("WildChat-1M-filter-1k","wildchat_1m"),("WildChat-4.8M-filter-1k","wildchat_4_8m")):
            for trace,events in wildchat_convert(SAMPLES/name,source):add(trace,events)
            print(source,source_counts[source],event_counts[source],flush=True)
        for index,item in enumerate(selected):
            path=item["transcript_path"];session_id=item["session_id"]
            trace_id=make_trace_id("swe_chat", index)
            matches=log_by_id[session_id];session_matches=session_by_id[session_id]
            if (len(matches)!=1 or len(session_matches)!=1 or
                matches[0]["transcript_path"]!=path or session_matches[0]["transcript_path"]!=path or
                matches[0]["compact_transcript_path"]!=item.get("compact_transcript_path")):
                raise ValueError(f"SWE sampled Session metadata mapping is ambiguous or inconsistent: {session_id}")
            session=session_matches[0]
            agent=session.get("agent") or "unknown"
            full_path=swe/path
            if not full_path.is_file():
                raise FileNotFoundError(f"filtered SWE sample main transcript missing: {full_path}")
            issues=[];fmt=None
            source_format=signature(full_path)
            if full_path.is_file():
                events,issues,fmt=swe_convert(full_path,trace_id)
                file_formats_by_agent[agent][fmt]+=1
                for _,r,rf in records(full_path):
                    formats_by_agent[agent][rf]+=1
                    if isinstance(r,dict):
                        types_by_agent[agent][str(r.get("type",r.get("event",r.get("role","NO_TYPE"))))]+=1
                    else:types_by_agent[agent][type(r).__name__]+=1
            if issues:failures.extend({"trace_id":trace_id,"path":path,**issue} for issue in issues)
            session_model=session.get("model") or None
            model_candidates=main_agent_model_candidates(full_path,source_format) if full_path.is_file() else set()
            model,model_basis=resolve_trace_model(session_model,model_candidates)
            model_resolution[model_basis]+=1
            if session_model and len(model_candidates)==1 and session_model!=model:
                model_resolution["session_metadata_differs_from_main_log"]+=1
                if len(model_disagreements)<10:
                    model_disagreements.append({"session_id":session_id,"session_model":session_model,
                                                "main_log_model":model})
            trace={"trace_id":trace_id,"source":"swe_chat","source_id":session_id,"query_type":None,
                   "language":None,"model":model,
                   "user_turn_count":count_user_turns(events,source_format)}
            add(trace,events,source_format)
            if (index+1)%100==0:print("swe_chat",index+1,"events",event_counts["swe_chat"],flush=True)
        flush()
    finally:
        trace_writer.close();event_writer.close()
    (HERE/"traces.parquet.tmp").replace(HERE/"traces.parquet")
    (HERE/"events.parquet.tmp").replace(HERE/"events.parquet")
    inspection["swe_raw_types_by_agent"]={k:dict(v) for k,v in types_by_agent.items()}
    inspection["swe_raw_formats_by_agent"]={k:dict(v) for k,v in formats_by_agent.items()}
    inspection["swe_file_formats_by_agent"]={k:dict(v) for k,v in file_formats_by_agent.items()}
    inspection["sample_manifest_revisions"]={name:manifest(SAMPLES/name)["source_revision"] for name in ("WildChat-1M-filter-1k","WildChat-4.8M-filter-1k","SWE-Chat-filter-1k")}
    inspection["swe_sampling_unit"]="session_id"
    inspection["swe_eligible_session_count"]=swe_manifest["eligible_session_count"]
    inspection["observed_quality"]={"missing_main_transcripts":sum(x.get("reason")=="missing_transcript" for x in failures),
                                    "invalid_jsonl_lines":sum(x.get("reason")=="invalid_jsonl" for x in failures),
                                    "null_or_empty_content_events":dict(null_content)}
    (HERE/"schema_inspection.json").write_text(json.dumps(inspection,ensure_ascii=False,indent=2,default=str)+"\n")
    report={"source_trace_counts":dict(source_counts),"source_event_counts":dict(event_counts),
            "swe_sampling_unit":"session_id","swe_eligible_session_count":swe_manifest["eligible_session_count"],
            "adapter_actions":dict(adapter_actions),
            "swe_model_resolution":{"counts":dict(model_resolution),"disagreement_examples":model_disagreements,
                                    "policy":"unique model on main-agent responses or turns wins; otherwise use a non-generic sessions.model; multi-model/unknown remains null"},
            "expected_traces_per_source":1000,
            "parse_failures":failures,"null_or_empty_content_events":dict(null_content),
            "unrecognized_or_supplementary_raw_types":[{"source":s,"type":t,"count":n} for (s,t),n in sorted(unrecognized.items())],
            "content_handling":{"wildchat_message_content":"exact source string, unchanged",
                                "swe_structured_payloads":"JSON serialized without truncation",
                                "invalid_jsonl_lines":"retained verbatim as metadata_event",
                                "intentional_posthoc_exclusions":"session outcome/summary labels and JSON document summary fields are not chronological events",
                                "user_body_tags_reinterpreted_as_other_events":0,
                                "xai_identical_user_chunks_in_one_source_group":"dropped without an event",
                                "discarded_leading_auxiliary_prefixes":transforms["discarded_leading_auxiliary_prefixes"],
                                "converter_truncations":0},
            "pre_projection_diagnostics":{"missing_event_timestamps":dict(missing_timestamps),
                                          "missing_source_event_ids":dict(missing_source_ids),
                                          "unmatched_tool_call_ids":unmatched_calls,
                                          "unmatched_tool_result_ids":unmatched_results,
                                          "unmatched_tool_call_ids_by_format":dict(unmatched_calls_by_format),
                                          "unmatched_tool_result_ids_by_format":dict(unmatched_results_by_format),
                                          "unmatched_tool_result_examples":unmatched_result_examples,
                                          "tool_result_precedes_later_call_ids":early_result_ids,
                                          "event_order_checked_before_removing_provenance_columns":True},
            "notes":["Unknown and supplementary raw records are represented as metadata_event with serialized raw payload.",
                     "SWE author attribution can be ambiguous when source lacks explicit authorship markers.",
                     "Document and message summary/outcome fields are excluded from chronological events because they may describe future session state."]}
    (HERE/"conversion_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("conversion complete",dict(source_counts),dict(event_counts),flush=True)


if __name__=="__main__":
    main()
