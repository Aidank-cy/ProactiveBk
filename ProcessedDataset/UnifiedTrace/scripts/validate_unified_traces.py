#!/usr/bin/env python3
"""Validate generated unified traces against the three sampled inputs."""
import collections
import hashlib
import json
import os
from pathlib import Path

import pyarrow.parquet as pq
import pyarrow as pa

from swe_format import signature
from swe_chat_adapter import EXCLUDED_FORMATS
from swe_chat_adapter import convert as swe_convert, count_user_turns, main_agent_model_candidates, resolve_trace_model
from trace_ids import trace_id as make_trace_id

HERE=Path(os.environ.get("UNIFIED_TRACE_OUTPUT_DIR",Path(__file__).resolve().parents[1]))
SAMPLES=Path(__file__).resolve().parents[3]/"OriginalDataset-filter-1k"
FILTERED=SAMPLES.parent/"OriginalDataset-filter"


def main():
    trace_arrow=pq.read_table(HERE/"traces.parquet")
    event_file=pq.ParquetFile(HERE/"events.parquet")
    query_field=trace_arrow.schema.field("query_type")
    traces=trace_arrow.to_pylist()
    errors=[];warnings=[];trace_by_id={}
    expected_trace_fields=["trace_id","source","source_id","query_type","language","model",
                           "user_turn_count"]
    if trace_arrow.schema.names!=expected_trace_fields:
        errors.append(f"traces.parquet columns differ from the seven-field schema: {trace_arrow.schema.names}")
    expected_event_fields=["trace_id","event_id","role","event_type","content","visibility"]
    if event_file.schema_arrow.names!=expected_event_fields:
        errors.append(f"events.parquet columns differ from the six-field schema: {event_file.schema_arrow.names}")
    if not pa.types.is_string(query_field.type) or not query_field.nullable:
        errors.append("query_type must be a nullable string column")
    query_type_null_count=sum(t["query_type"] is None for t in traces)
    if query_type_null_count!=len(traces):
        errors.append(f"query_type contains {len(traces)-query_type_null_count} non-null labels; source samples provide no benchmark taxonomy labels")
    for t in traces:
        if t["trace_id"] in trace_by_id:errors.append(f"duplicate trace_id: {t['trace_id']}")
        trace_by_id[t["trace_id"]]=t
    source_counts=collections.Counter(t["source"] for t in traces)
    for source in ("wildchat_1m","wildchat_4_8m","swe_chat"):
        if source_counts[source]!=1000:errors.append(f"{source}: {source_counts[source]} traces, expected 1000")
    for source in ("wildchat_1m","wildchat_4_8m"):
        source_ids=[t["source_id"] for t in traces if t["source"]==source]
        if len(set(source_ids))!=len(source_ids):errors.append(f"{source}: duplicate conversation_hash in filtered sample")
    manifests={name:json.loads((SAMPLES/name/"sample_manifest.json").read_text()) for name in ("WildChat-1M-filter-1k","WildChat-4.8M-filter-1k","SWE-Chat-filter-1k")}
    swe_manifest=manifests["SWE-Chat-filter-1k"]
    swe_selected=swe_manifest["selected"]
    swe_ids=[item["session_id"] for item in swe_selected]
    swe_paths=[item["transcript_path"] for item in swe_selected]
    if swe_manifest.get("sampling_unit")!="session_id":errors.append("SWE sampling unit is not session_id")
    if len(swe_ids)!=1000 or len(set(swe_ids))!=1000:errors.append("SWE manifest does not contain 1000 distinct Session IDs")
    if len(set(swe_paths))!=len(swe_paths):errors.append("SWE manifest contains shared main transcript paths")
    swe_sessions=pq.read_table(SAMPLES/"SWE-Chat-filter-1k"/"sessions.parquet",columns=["session_id","transcript_path","model"]).to_pylist()
    swe_logs=pq.read_table(SAMPLES/"SWE-Chat-filter-1k"/"session_logs.parquet",columns=["session_id","transcript_path","compact_transcript_path"]).to_pylist()
    if len(swe_sessions)!=1000 or len(swe_logs)!=1000:errors.append("SWE sampled metadata tables must each have 1000 rows")
    for i,item in enumerate(swe_selected):
        if i>=len(swe_sessions) or i>=len(swe_logs):break
        if (swe_sessions[i]["session_id"]!=item["session_id"] or swe_logs[i]["session_id"]!=item["session_id"] or
            swe_sessions[i]["transcript_path"]!=item["transcript_path"] or swe_logs[i]["transcript_path"]!=item["transcript_path"] or
            swe_logs[i]["compact_transcript_path"]!=item["compact_transcript_path"]):
            errors.append(f"SWE sample metadata mapping mismatch at index {i}")
        if not (SAMPLES/"SWE-Chat-filter-1k"/item["transcript_path"]).is_file():errors.append(f"SWE sampled transcript missing: {item['transcript_path']}")
    swe_trace_ids=[t["source_id"] for t in traces if t["source"]=="swe_chat"]
    if len(swe_trace_ids)!=1000 or set(swe_trace_ids)!=set(swe_ids):errors.append("SWE unified traces do not map one-to-one to selected Session IDs")
    swe_selected_by_id={item["session_id"]:item for item in swe_selected}
    swe_formats=collections.Counter()
    for item in swe_selected:
        source_format=signature(SAMPLES/"SWE-Chat-filter-1k"/item["transcript_path"])
        swe_formats[source_format]+=1
        if item.get("format_family")!=source_format or not item.get("structural_variant"):
            errors.append(f"SWE selected Session format/variant provenance mismatch: {item['session_id']}")
        if source_format in EXCLUDED_FORMATS or source_format=="unclassified":
            errors.append(f"SWE selected Session has excluded source format: {item['session_id']} ({source_format})")
    if swe_manifest.get("sampling_strategy")!="balanced_cli_family_then_structural_variant_round_robin":
        errors.append("SWE sample is not stratified by CLI family and structural variant")
    if swe_manifest.get("sampled_format_quotas")!=dict(swe_formats) or len(swe_formats)!=14:
        errors.append(f"SWE sampled format coverage differs from 14-family allocation: {dict(swe_formats)}")
    profile_path=Path(swe_manifest.get("sampling_profile") or "")
    if not profile_path.is_file():
        errors.append("SWE sampling profile is missing")
    else:
        with profile_path.open("rb") as stream:
            profile_hash=hashlib.file_digest(stream,"sha256").hexdigest()
        if profile_hash!=swe_manifest.get("sampling_profile_sha256"):
            errors.append("SWE sampling profile hash differs from sample manifest")
    filtered_swe_manifest=FILTERED/"SWE-Chat-filter"/"filter_manifest.json"
    if hashlib.sha256(filtered_swe_manifest.read_bytes()).hexdigest()!=swe_manifest.get("filtered_source_manifest_sha256"):
        errors.append("SWE filtered source manifest hash differs from sample manifest")
    swe_session_by_id={row["session_id"]:row for row in swe_sessions}
    expected_wild={}
    for name,source in (("WildChat-1M-filter-1k","wildchat_1m"),("WildChat-4.8M-filter-1k","wildchat_4_8m")):
        rows=pq.read_table(SAMPLES/name/"train.parquet",columns=["conversation_hash","conversation","language","model"]).to_pylist()
        selected_indices=manifests[name]["selected"]
        if len(rows)!=1000 or len(selected_indices)!=1000:errors.append(f"{name}: sampled rows or manifest length is not 1000")
        source_dir=FILTERED/name.removesuffix("-1k")
        original_indices=pq.read_table(source_dir/"kept_original_indices.parquet").take(pa.array(selected_indices,type=pa.int64())).column("original_global_row_index").to_pylist()
        if manifests[name].get("selected_original_global_row_indices")!=original_indices:
            errors.append(f"{name}: original source row provenance differs from filtered index mapping")
        source_manifest=json.loads((source_dir/"filter_manifest.json").read_text())
        if source_manifest["source_revision"]!=manifests[name]["source_revision"]:
            errors.append(f"{name}: filtered source revision mismatch")
        for index,row in enumerate(rows):
            expected_id=make_trace_id(source,index)
            expected_wild[expected_id]=(source,row)
    swe_index_by_id={item["session_id"]:index for index,item in enumerate(swe_selected)}
    for t in traces:
        if t["source"]=="swe_chat":
            sel=swe_selected_by_id.get(t["source_id"])
            if sel is None:errors.append(f"{t['trace_id']}: SWE Session ID absent from manifest");continue
            expected=make_trace_id("swe_chat",swe_index_by_id[sel["session_id"]])
            session_model=swe_session_by_id[t["source_id"]]["model"] or None
            path=SAMPLES/"SWE-Chat-filter-1k"/sel["transcript_path"]
            candidates=main_agent_model_candidates(path,signature(path))
            expected_model,_=resolve_trace_model(session_model,candidates)
            if t["model"]!=expected_model:
                errors.append(f"{t['trace_id']}: SWE model mismatch")
        else:
            original=expected_wild.get(t["trace_id"])
            if original is None:errors.append(f"{t['trace_id']}: WildChat trace ID absent from sampled rows");continue
            expected_source,row=original
            if t["source"]!=expected_source or t["source_id"]!=row["conversation_hash"]:
                errors.append(f"{t['trace_id']}: WildChat source or conversation hash mismatch")
            if t["language"]!=row["language"] or t["model"]!=row["model"]:
                errors.append(f"{t['trace_id']}: WildChat language/model mismatch")
            expected=t["trace_id"]
        if t["trace_id"]!=expected:errors.append(f"{t['trace_id']}: unstable trace ID")
    next_id=collections.Counter();users=collections.Counter();event_counts=collections.Counter();swe_event_hashes={}
    swe_with_content=set()
    null_content=collections.Counter();unusual=collections.Counter();wild_content=collections.defaultdict(list)
    for batch in event_file.iter_batches(batch_size=4096):
        for e in batch.to_pylist():
            tid=e["trace_id"];t=trace_by_id.get(tid)
            if t is None:errors.append(f"event references missing trace: {tid}");continue
            if e["event_id"]!=next_id[tid]:errors.append(f"{tid}: event_id {e['event_id']} expected {next_id[tid]}")
            next_id[tid]+=1;event_counts[t["source"]]+=1
            if e["event_type"]=="user_message" and e["role"]=="user":users[tid]+=1
            if t["source"]=="swe_chat":
                if (e["event_type"] in ("user_message","assistant_message","assistant_thinking","tool_call","tool_result")
                        and e["content"] is not None and str(e["content"]).strip()):
                    swe_with_content.add(tid)
                digest=swe_event_hashes.get(tid)
                if digest is None:
                    digest=hashlib.sha256()
                    swe_event_hashes[tid]=digest
                digest.update(json.dumps((e["event_id"],e["role"],e["event_type"],e["content"],e["visibility"]),ensure_ascii=False,separators=(",",":")).encode("utf-8"))
            if e["content"] is None or e["content"]=="":null_content[t["source"]]+=1
            if t["source"]!="swe_chat" and e["event_type"] in ("user_message","assistant_message"):
                wild_content[tid].append((e["role"],e["content"]))
            if e["event_type"]=="user_message" and e["role"]!="user":unusual["user_message_wrong_role"]+=1
    for tid,t in trace_by_id.items():
        if next_id[tid]==0:errors.append(f"{tid}: trace has no events")
        if t["source"]=="swe_chat" and tid not in swe_with_content:
            errors.append(f"{tid}: trace has no extractable interaction content")
        if t["source"]!="swe_chat" and users[tid]!=t["user_turn_count"]:
            errors.append(f"{tid}: user_turn_count mismatch")
        if tid in expected_wild:
            original_messages=expected_wild[tid][1]["conversation"] or []
            expected_content=[(m["role"],m["content"]) for m in original_messages]
            if wild_content[tid]!=expected_content:errors.append(f"{tid}: WildChat message order or content mismatch")
            if not any(role in ("user","assistant") and isinstance(body,str) and body.strip()
                       for role,body in expected_content):
                errors.append(f"{tid}: WildChat Conversation has no interaction content")
    for item in swe_selected:
        session_id=item["session_id"]
        tid=make_trace_id("swe_chat",swe_index_by_id[session_id])
        trace=trace_by_id.get(tid)
        if trace is None:
            errors.append(f"missing SWE trace for sampled Session {session_id}")
            continue
        path=SAMPLES/"SWE-Chat-filter-1k"/item["transcript_path"]
        if not path.is_file():continue
        source_events,issues,_=swe_convert(path,tid)
        expected_user_turns=count_user_turns(source_events,signature(path))
        if trace["user_turn_count"]!=expected_user_turns:
            errors.append(f"{tid}: human user message count differs from raw transcript")
        if next_id[tid]!=len(source_events):
            errors.append(f"{tid}: normalized event count differs from raw transcript")
        source_digest=hashlib.sha256()
        for e in source_events:
            source_digest.update(json.dumps((e["event_id"],e["role"],e["event_type"],e["content"],e["visibility"]),ensure_ascii=False,separators=(",",":")).encode("utf-8"))
        stored_digest=swe_event_hashes[tid] if tid in swe_event_hashes else hashlib.sha256()
        if stored_digest.digest()!=source_digest.digest():
            errors.append(f"{tid}: stored events differ from source transcript conversion")
    def duplicates(values):
        grouped=collections.defaultdict(list)
        for key,tid in values:grouped[key].append(tid)
        return [{"value":key,"trace_ids":ids} for key,ids in grouped.items() if len(ids)>1]
    wild=[t for t in traces if t["source"]!="swe_chat"]
    hash_dups=duplicates((t["source_id"],t["trace_id"]) for t in wild if t["source_id"])
    norm_dups=duplicates((hashlib.sha256(json.dumps(wild_content[t["trace_id"]],ensure_ascii=False,separators=(",",":")).encode()).hexdigest(),t["trace_id"]) for t in wild)
    cross_hash=[x for x in hash_dups if len({trace_by_id[tid]["source"] for tid in x["trace_ids"]})>1]
    cross_content=[x for x in norm_dups if len({trace_by_id[tid]["source"] for tid in x["trace_ids"]})>1]
    report=json.loads((HERE/"conversion_report.json").read_text())
    diagnostics=report.get("pre_projection_diagnostics",{})
    unmatched_results=diagnostics.get("unmatched_tool_result_ids")
    unmatched_calls=diagnostics.get("unmatched_tool_call_ids")
    unusual["tool_result_precedes_later_call_ids"]=diagnostics.get("tool_result_precedes_later_call_ids")
    if not diagnostics.get("event_order_checked_before_removing_provenance_columns"):
        errors.append("conversion did not report pre-projection event-order validation")
    if unmatched_results:warnings.append(f"{unmatched_results} tool result IDs have no matching call ID in the same main trace")
    if unmatched_calls:warnings.append(f"{unmatched_calls} tool call IDs have no matching result ID in the same main trace")
    report["validation"]={"passed":not errors,"errors":errors[:100],"error_count":len(errors),"warnings":warnings,
                          "trace_counts":dict(source_counts),"event_counts":dict(event_counts),
                          "swe_distinct_session_ids":len(set(swe_trace_ids)),
                          "swe_sampled_format_counts":dict(swe_formats),
                          "query_type_null_count":query_type_null_count,"query_type_expected_null_count":len(traces),
                          "missing_event_timestamps_before_projection":diagnostics.get("missing_event_timestamps"),
                          "missing_source_event_ids_before_projection":diagnostics.get("missing_source_event_ids"),
                          "null_or_empty_content_events":dict(null_content),"unusual_sequences":dict(unusual),
                          "unmatched_tool_result_ids":unmatched_results,"unmatched_tool_call_ids":unmatched_calls,
                          "duplicate_conversation_hash_groups":len(hash_dups),"duplicate_normalized_content_groups":len(norm_dups),
                          "cross_dataset_hash_overlap_groups":len(cross_hash),"cross_dataset_content_overlap_groups":len(cross_content),
                          "duplicate_hash_examples":hash_dups[:10],"duplicate_content_examples":norm_dups[:10]}
    (HERE/"conversion_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report["validation"],ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)


if __name__=="__main__":main()
