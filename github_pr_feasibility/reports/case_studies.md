# Retrieved PR case studies

These are original GitHub development records, not Agent interaction traces. Current titles and bodies may have been edited.

## [firezone/firezone#4133](https://github.com/firezone/firezone/pull/4133)

- Original task candidate: feat(apple): Handle network changes reliably on macOS and iOS (current title, temporal availability unverified).
- Development history: opened 2024-03-13T21:30:39Z; 14 commits; 24 formal reviews; merged 2024-03-27T03:13:45Z.
- Chronological evidence:
  - 2024-03-13T21:30:39Z pr_opened by jamilbk: (no stable text) ([source](https://github.com/firezone/firezone/pull/4133)).
  - 2024-03-13T21:30:45Z issue_comment by vercel[bot]: [vc]: #9LMPcRsr9BlIC7UiHiSoXhK2TeHHH1+FpP3s1xQM/xw=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0eXBlIjoiZ2l0aHViIiwicHJvamVjdHMiOlt7Im5hbWUiOiJmaXJlem9uZSIsImluc3BlY3RvclVybCI6 ([source](https://github.com/firezone/firezone/pull/4133#issuecomment-1995894349)).
  - 2024-03-13T21:32:33Z issue_comment by github-actions[bot]: #### Terraform Cloud Plan Output ``` Plan: 9 to add, 8 to change, 9 to destroy. ``` [Terraform Cloud Plan](https://app.terraform.io/app/firezone/workspaces/stag ([source](https://github.com/firezone/firezone/pull/4133#issuecomment-1995899703)).
  - 2024-03-13T21:41:20Z issue_comment by github-actions[bot]: ### Performance Test Results #### TCP | Test Name | Received/s | Sent/s | Retransmits | |---|---|---|---| | direct-tcp-client2server | 225.5 MiB (+3%) | 227.0 M ([source](https://github.com/firezone/firezone/pull/4133#issuecomment-1995912944)).
  - 2024-03-17T14:44:22Z issue_comment by jamilbk: @conectado @ReactorScram @thomaseizinger Just want to leave this here as an example of how noisy the path update handler can be. This was all printed from a sin ([source](https://github.com/firezone/firezone/pull/4133#issuecomment-2002495689)).
  - 2024-03-17T20:51:50Z review_comment by jamilbk: Each path update callback spawns a thread (`workQueue.async`), so we're ok to block here with a semaphore. ([source](https://github.com/firezone/firezone/pull/4133#discussion_r1527612400)).
  - 2024-03-17T20:53:53Z review by jamilbk: (no stable text) ([source](https://github.com/firezone/firezone/pull/4133#pullrequestreview-1941585245)).
  - 2024-03-17T21:37:29Z issue_comment by thomaseizinger: > @conectado @ReactorScram @thomaseizinger Just want to leave this here as an example of how noisy the path update handler can be Thanks, that is really helpful ([source](https://github.com/firezone/firezone/pull/4133#issuecomment-2002625521)).
  - 2024-03-18T13:56:17Z issue_comment by jamilbk: > Should connlib wait 500ms Yeah I think 500ms is a reasonable debounce timeout to start with. ([source](https://github.com/firezone/firezone/pull/4133#issuecomment-2003986649)).
  - 2024-03-19T00:42:05Z review_comment by thomaseizinger: Do you now just assume that the tunnel is ready after `connect`? I think that makes sense. I guess `connlib` should fail using `on_disconnect` if we cannot init ([source](https://github.com/firezone/firezone/pull/4133#discussion_r1529525071)).
  - 2024-03-19T00:43:23Z review by thomaseizinger: Great work! I don't fully understand all the swift stuff but I have one question regarding `on_tunnel_ready`. ([source](https://github.com/firezone/firezone/pull/4133#pullrequestreview-1944694581)).
  - 2024-03-19T00:44:00Z review by thomaseizinger: (no stable text) ([source](https://github.com/firezone/firezone/pull/4133#pullrequestreview-1944699084)).
- Candidate cutoff: 2024-03-26T17:16:59Z, commit `13b3765f7d361ae35268ffc8ae4d685c9dc77547`; state evidence: review_associated_commit.
- Explicit earlier requirements: > @conectado @ReactorScram @thomaseizinger Just want to leave this here as an example of how noisy the path update handler can be Thanks, that is really helpful! Should connlib wait 500ms after receiving an update before it acts on it? I.e. a new update coming in would reset the timer to 0. That appears it would end up only apply a single one of these then. > Should connlib wait 500ms Yeah I think 500ms is a reasonable debounce timeout to start with. Great work! I don't fully understand all the
- Later human feedback: This was hard to understand, so I asked ChatGPT and tried to look it up in the Apple docs (https://developer.apple.com/documentation/combine/published) and this is what I heard: - The `$` sigil means `status` is a Published property that can be subscribed to. - `receive` means we are subscribing to it - ChatGPT says `mainQueue` refers to a process-wide main thread (interchangeably called a 'queue') for processing UI events. I've seen the same pattern with Qt's signals and slots, and C# / .NET's ([source](https://github.com/firezone/firezone/pull/4133#discussion_r1539766956)).
- Potential implicit intent: missing_edge_case (heuristic; inferability=possible; relevance=possible).
- Later change evidence: verified=none; possible later-review commit=none (causal timing unverified).
- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain.
- Provisional suitability: B; reasons: NO_VERIFIED_POST_FEEDBACK_REVISION.

## [firezone/firezone#5675](https://github.com/firezone/firezone/pull/5675)

- Original task candidate: feat(blog): explain the sans-IO design pattern (current title, temporal availability unverified).
- Development history: opened 2024-07-02T01:50:47Z; 47 commits; 25 formal reviews; merged 2024-07-03T12:40:07Z.
- Chronological evidence:
  - 2024-07-02T01:50:47Z pr_opened by thomaseizinger: (no stable text) ([source](https://github.com/firezone/firezone/pull/5675)).
  - 2024-07-02T01:50:50Z issue_comment by vercel[bot]: [vc]: #bGaObHZp4kjo38Xi9vhluFOtx/tZ1R2rkCYhEYRkjGQ=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0eXBlIjoiZ2l0aHViIiwicHJvamVjdHMiOlt7Im5hbWUiOiJmaXJlem9uZSIsImluc3BlY3RvclVybCI6 ([source](https://github.com/firezone/firezone/pull/5675#issuecomment-2201653631)).
  - 2024-07-02T01:52:45Z issue_comment by github-actions[bot]: #### Terraform Cloud Plan Output ``` Plan: 15 to add, 23 to change, 15 to destroy. ``` [Terraform Cloud Plan](https://app.terraform.io/app/firezone/workspaces/s ([source](https://github.com/firezone/firezone/pull/5675#issuecomment-2201656169)).
  - 2024-07-02T02:00:43Z issue_comment by github-actions[bot]: ### Performance Test Results #### TCP | Test Name | Received/s | Sent/s | Retransmits | |---|---|---|---| | direct-tcp-client2server | 233.9 MiB (+0%) | 235.6 M ([source](https://github.com/firezone/firezone/pull/5675#issuecomment-2201667022)).
  - 2024-07-02T07:18:00Z issue_comment by thomaseizinger: @jamilbk The deployment seems to fail but I don't have access to the build log. ([source](https://github.com/firezone/firezone/pull/5675#issuecomment-2202144408)).
  - 2024-07-02T08:44:14Z issue_comment by thomaseizinger: @conectado @ReactorScram Feel free to already have a read through if you'd like. Free-text reviews can attract a lot of feedback so I'd prefer to do 1-2 rounds  ([source](https://github.com/firezone/firezone/pull/5675#issuecomment-2202340339)).
  - 2024-07-02T08:45:53Z review_comment by thomaseizinger: ```suggestion You can find all of these snippets as working programs in the following repository: https://github.com/firezone/sans-io-blog-example. ``` ([source](https://github.com/firezone/firezone/pull/5675#discussion_r1662107121)).
  - 2024-07-02T08:45:54Z review by thomaseizinger: (no stable text) ([source](https://github.com/firezone/firezone/pull/5675#pullrequestreview-2153132377)).
  - 2024-07-02T08:46:19Z review_comment by thomaseizinger: I have the repo ready locally but don't have permission to make one. ([source](https://github.com/firezone/firezone/pull/5675#discussion_r1662107744)).
  - 2024-07-02T08:46:20Z review by thomaseizinger: (no stable text) ([source](https://github.com/firezone/firezone/pull/5675#pullrequestreview-2153133379)).
  - 2024-07-02T08:46:58Z review by thomaseizinger: (no stable text) ([source](https://github.com/firezone/firezone/pull/5675#pullrequestreview-2153134856)).
  - 2024-07-02T08:46:58Z review_comment by thomaseizinger: These need to be filled in after publishing. ([source](https://github.com/firezone/firezone/pull/5675#discussion_r1662108700)).
- Candidate cutoff: 2024-07-03T12:26:52Z, commit `8a309ea04bcbd93e0465fcdf730e22b55b2e4d36`; state evidence: prior_review_associated_commit.
- Explicit earlier requirements: @jamilbk The deployment seems to fail but I don't have access to the build log. @conectado @ReactorScram Feel free to already have a read through if you'd like. Free-text reviews can attract a lot of feedback so I'd prefer to do 1-2 rounds of feedback & editing with @jamilbk first and then get more input from you! These need to be filled in after publishing. I skimmed through it, looks interesting. I was thinking of that other blog you were drafting about the `poll_*` pattern vs. writing async f
- Later human feedback: > > > Will do one final pass first thing tomorrow and approve to get this published. When do you want to share to socials? Thursday? > > > > > > I was thinking we could: > > ``` > > * Publish on website tomorrow > > > > * See if we make it into this week's TWIR > > > > * If yes, publish to socials and update post with links to HN and Reddit for comments > > > > * If no, wait a week before publishing to socials > > ``` > > If we can't link to the HN thread directly, then this is completely unnece ([source](https://github.com/firezone/firezone/pull/5675#issuecomment-2205958713)).
- Potential implicit intent: new_constraint (heuristic; inferability=possible; relevance=possible).
- Later change evidence: verified=none; possible later-review commit=none (causal timing unverified).
- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain.
- Provisional suitability: B; reasons: NO_VERIFIED_POST_FEEDBACK_REVISION.

## [firezone/firezone#13920](https://github.com/firezone/firezone/pull/13920)

- Original task candidate: feat(connlib): track gateway flows with token attribution (current title, temporal availability unverified).
- Development history: opened 2026-06-29T01:59:31Z; 30 commits; 46 formal reviews; merged 2026-07-09T13:04:41Z.
- Chronological evidence:
  - 2026-06-29T01:59:31Z pr_opened by jamilbk: (no stable text) ([source](https://github.com/firezone/firezone/pull/13920)).
  - 2026-06-29T03:36:50Z issue_comment by jamilbk: I have not scanned through this one yet, so just a directionality check is requested. ([source](https://github.com/firezone/firezone/pull/13920#issuecomment-4828750007)).
  - 2026-06-29T09:08:41Z review_comment by thomaseizinger: Should this get grouped into a dedicated struct? ([source](https://github.com/firezone/firezone/pull/13920#discussion_r3490514740)).
  - 2026-06-29T09:40:36Z review_comment by thomaseizinger: Why are we even writing the config when the interval is 0? ([source](https://github.com/firezone/firezone/pull/13920#discussion_r3490714415)).
  - 2026-06-29T09:41:07Z review_comment by thomaseizinger: Should spawn call prune on start? ([source](https://github.com/firezone/firezone/pull/13920#discussion_r3490717700)).
  - 2026-06-29T09:42:15Z review_comment by thomaseizinger: Do we still need this separate gate? I.e. do we want to allow customers to disable flow logging on a gateway even if they enable it via the portal? That sounds  ([source](https://github.com/firezone/firezone/pull/13920#discussion_r3490724741)).
  - 2026-06-29T09:44:23Z review_comment by thomaseizinger: Is symbol reference stutters, either fully import it or strip `FlowLog` from `FlowLogRecord`. The latter is what we aim for most of the time. ([source](https://github.com/firezone/firezone/pull/13920#discussion_r3490737992)).
  - 2026-06-29T09:48:41Z review_comment by thomaseizinger: Why does this work differently than it does on the Gateway? What is the reason we moved away from the TLS-based design? The core idea of the TLS-based design is ([source](https://github.com/firezone/firezone/pull/13920#discussion_r3490768792)).
  - 2026-06-29T09:51:36Z review by thomaseizinger: Stopping here for now. This is quite entangled with some of the other changes / feedback so I think we'll have to land a few things first before it makes sense  ([source](https://github.com/firezone/firezone/pull/13920#pullrequestreview-4590378666)).
  - 2026-06-30T13:03:06Z issue_comment by jamilbk: > Primarily, I want to understand why we moved away from the TLS-based design. Unless I am missing something, I don't see a reason why this needs to work differ ([source](https://github.com/firezone/firezone/pull/13920#issuecomment-4843759939)).
  - 2026-07-01T22:00:58Z issue_comment by thomaseizinger: > I am probably missing context around "many exit paths" though. Why wouldn't counting at the encap/decap sites be enough especially now that we encrypt directl ([source](https://github.com/firezone/firezone/pull/13920#issuecomment-4860375992)).
  - 2026-07-02T14:08:55Z review_comment by Copilot: FlowLogsConfig::enabled treats api_url: Some("") as enabled (if interval > 0). That can lead to persisting an empty URL and an uploader that repeatedly fails to ([source](https://github.com/firezone/firezone/pull/13920#discussion_r3513695901)).
- Candidate cutoff: 2026-07-20T06:21:03Z, commit `193dab5d9b9215cb94c64ca8a7da7e16f292e8f4`; state evidence: prior_review_associated_commit.
- Explicit earlier requirements: I have not scanned through this one yet, so just a directionality check is requested. Stopping here for now. This is quite entangled with some of the other changes / feedback so I think we'll have to land a few things first before it makes sense to continue here. Primarily, I want to understand why we moved away from the TLS-based design. Unless I am missing something, I don't see a reason why this needs to work differently on the Client than it does on the Gateway. This is coming in a later PR.
- Later human feedback: > PR is a bit large - curious if it's making sense or we need to divide it up again. Yeah I was thinking the same. I wasn't happy with how we are doing the routing and refactored it a fair bit. I think it is much simpler now. Currently checking what bugs I introduced. We might be able to extract something but I am not sure. I'll have a look tomorrow. ([source](https://github.com/firezone/firezone/pull/13968#issuecomment-5019349570)).
- Potential implicit intent: new_requirement (heuristic; inferability=possible; relevance=possible).
- Later change evidence: verified=none; possible later-review commit=none (causal timing unverified).
- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain.
- Provisional suitability: B; reasons: NO_VERIFIED_POST_FEEDBACK_REVISION.

## [firezone/firezone#11820](https://github.com/firezone/firezone/pull/11820)

- Original task candidate: feat(apple): headless macOS client (current title, temporal availability unverified).
- Development history: opened 2026-01-23T20:37:55Z; 57 commits; 23 formal reviews; merged 2026-08-01T01:50:44Z.
- Chronological evidence:
  - 2026-01-23T20:37:55Z pr_opened by Copilot: (no stable text) ([source](https://github.com/firezone/firezone/pull/11820)).
  - 2026-01-23T20:38:00Z issue_comment by vercel[bot]: [vc]: #Yl8SGQxFd8hsYGer8RtNBdYJB/oxCJ2IjQMhLLvaNpA=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0eXBlIjoiZ2l0aHViIiwicHJvamVjdHMiOlt7Im5hbWUiOiJmaXJlem9uZSIsInByb2plY3RJZCI6InBy ([source](https://github.com/firezone/firezone/pull/11820#issuecomment-3792303354)).
  - 2026-01-24T16:59:34Z review by jamilbk: @copilot we want to go the network extension route so that the deploy / management semantics don't require root, and so that we can reuse all of our Network Ext ([source](https://github.com/firezone/firezone/pull/11820#pullrequestreview-3702062530)).
  - 2026-01-24T17:01:03Z issue_comment by Copilot: > @copilot we want to go the network extension route so that the deploy / management semantics don't require root, and so that we can reuse all of our Network E ([source](https://github.com/firezone/firezone/pull/11820#issuecomment-3795087359)).
  - 2026-01-26T16:04:33Z issue_comment by jamilbk: @copilot We want the same API being introduced here for the linux and windows headless clients: https://github.com/firezone/firezone/pull/11882 Connect and disc ([source](https://github.com/firezone/firezone/pull/11820#issuecomment-3800379291)).
  - 2026-01-26T16:09:37Z issue_comment by Copilot: > @copilot > > We want the same API being introduced here for the linux and windows headless clients: ... Updated to match the API from PR #11882. Changes in co ([source](https://github.com/firezone/firezone/pull/11820#issuecomment-3800405673)).
  - 2026-01-26T16:41:15Z review_comment by jamilbk: ```suggestion Firezone - Headless ZTNA Client ``` ([source](https://github.com/firezone/firezone/pull/11820#discussion_r2728364010)).
  - 2026-01-26T16:41:36Z review_comment by jamilbk: ```suggestion When run without a subcommand, connects to Firezone and starts the tunnel. ``` ([source](https://github.com/firezone/firezone/pull/11820#discussion_r2728365706)).
  - 2026-01-26T16:41:43Z review_comment by jamilbk: ```suggestion ``` ([source](https://github.com/firezone/firezone/pull/11820#discussion_r2728366244)).
  - 2026-01-26T16:44:14Z review by jamilbk: Bundle id of NetworkExtension is `dev.firezone.firezone.network-extension`. We also need to install the system extension - see how the host app does this. We sh ([source](https://github.com/firezone/firezone/pull/11820#pullrequestreview-3706932467)).
  - 2026-01-26T16:48:08Z issue_comment by Copilot: > Bundle id of NetworkExtension is `dev.firezone.firezone.network-extension`. > > We also need to install the system extension - see how the host app does this. ([source](https://github.com/firezone/firezone/pull/11820#issuecomment-3800593896)).
  - 2026-01-26T16:48:11Z review by copilot-swe-agent[bot]: (no stable text) ([source](https://github.com/firezone/firezone/pull/11820#pullrequestreview-3706966467)).
- Candidate cutoff: 2026-07-31T23:12:25Z, commit `5bacd63845a035f42a027d704f4230ff95d3a75e`; state evidence: prior_review_associated_commit.
- Explicit earlier requirements: @copilot we want to go the network extension route so that the deploy / management semantics don't require root, and so that we can reuse all of our Network Extension logic @copilot We want the same API being introduced here for the linux and windows headless clients: https://github.com/firezone/firezone/pull/11882 Connect and disconnect is implied Bundle id of NetworkExtension is `dev.firezone.firezone.network-extension`. We also need to install the system extension - see how the host app does
- Later human feedback: @thomaseizinger Turns out we were going about this completely the wrong way. Adding a second app bundle means we need to embed _another_ copy of the network extension in that bundle in order to control it. This effectively creates two Firezone VPNs on the same system. We could get around that by re-using the exact same bundle ID as the GUI app (this is the approach taken in this PR), but app store expressly enforces each signed binary to have a unique bundle identifier, so this build would have ([source](https://github.com/firezone/firezone/pull/11820#issuecomment-5148231111)).
- Potential implicit intent: bug_report (heuristic; inferability=possible; relevance=possible).
- Later change evidence: verified=none; possible later-review commit=3b25d27e0eab874f8597ecb7b29e9b6e128bd79e (causal timing unverified).
- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain.
- Provisional suitability: B; reasons: POSSIBLE_BUT_UNVERIFIED_REVISION.

## [firezone/firezone#4779](https://github.com/firezone/firezone/pull/4779)

- Original task candidate: feat(connlib): traffic filtering (current title, temporal availability unverified).
- Development history: opened 2024-04-24T22:47:55Z; 62 commits; 30 formal reviews; merged 2024-05-07T20:03:29Z.
- Chronological evidence:
  - 2024-04-24T22:47:55Z pr_opened by conectado: (no stable text) ([source](https://github.com/firezone/firezone/pull/4779)).
  - 2024-04-24T22:48:01Z issue_comment by vercel[bot]: [vc]: #UeauxRWsYz+zxOVgdrga8WlGD6hhFRewq9Kl07zOr3E=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0eXBlIjoiZ2l0aHViIiwicHJvamVjdHMiOlt7Im5hbWUiOiJmaXJlem9uZSIsImluc3BlY3RvclVybCI6 ([source](https://github.com/firezone/firezone/pull/4779#issuecomment-2075974970)).
  - 2024-04-24T22:49:34Z issue_comment by github-actions[bot]: #### Terraform Cloud Plan Output ``` Plan: 15 to add, 15 to change, 15 to destroy. ``` [Terraform Cloud Plan](https://app.terraform.io/app/firezone/workspaces/s ([source](https://github.com/firezone/firezone/pull/4779#issuecomment-2075978705)).
  - 2024-04-24T23:28:18Z review_comment by conectado: This has some implications: If you have multiple overlaping CIDRs allowing traffic for a given ip, the most specific resource's traffic filters would be used. @ ([source](https://github.com/firezone/firezone/pull/4779#discussion_r1578628035)).
  - 2024-04-24T23:28:19Z review by conectado: (no stable text) ([source](https://github.com/firezone/firezone/pull/4779#pullrequestreview-2021118628)).
  - 2024-04-25T00:14:01Z review by jamilbk: (no stable text) ([source](https://github.com/firezone/firezone/pull/4779#pullrequestreview-2021166328)).
  - 2024-04-25T00:14:01Z review_comment by jamilbk: Would it not combine the rules? For example, `10.0.0.0/24` -> Allow `tcp/80` `10.0.0.1/32` -> Allow `tcp/443` `10.0.0.1/32` would allow both `tcp/80` and `tcp/4 ([source](https://github.com/firezone/firezone/pull/4779#discussion_r1578656270)).
  - 2024-04-25T01:11:54Z review by conectado: (no stable text) ([source](https://github.com/firezone/firezone/pull/4779#pullrequestreview-2021206584)).
  - 2024-04-25T01:11:54Z review_comment by conectado: We can do that but it requires some extra work, it would mean calculating what cidr are within another and adding those rules or iterating through all matches w ([source](https://github.com/firezone/firezone/pull/4779#discussion_r1578682709)).
  - 2024-04-25T03:45:57Z review by jamilbk: (no stable text) ([source](https://github.com/firezone/firezone/pull/4779#pullrequestreview-2021427119)).
  - 2024-04-25T03:45:57Z review_comment by jamilbk: Could these be compiled into an efficient lookup structure whenever resources are updated or a DNS is resolved? ([source](https://github.com/firezone/firezone/pull/4779#discussion_r1578809165)).
  - 2024-04-25T04:36:20Z review by conectado: (no stable text) ([source](https://github.com/firezone/firezone/pull/4779#pullrequestreview-2021471003)).
- Candidate cutoff: 2024-05-03T15:29:16Z, commit `3965b6b90d6f59594791ddcbbaf3548ecf7b5cd5`; state evidence: prior_review_associated_commit.
- Explicit earlier requirements: Would it not combine the rules? For example, `10.0.0.0/24` -> Allow `tcp/80` `10.0.0.1/32` -> Allow `tcp/443` `10.0.0.1/32` would allow both `tcp/80` and `tcp/443`? We can do that but it requires some extra work, it would mean calculating what cidr are within another and adding those rules or iterating through all matches with each packet. If we want to do it I would go for the former although it's a bit harder to implement since this runs on the hot path. Could these be compiled into an efficie
- Later human feedback: > > > @AndrewDryga I just realized that now we can get some filters with messages "all", does it still mean that empty filters means allow all or allow none? > > > > > > It should be permit all. Deny all is what happens when there's no policy. > > If that's the case I rhink we should remove the "all" value for filters. Having 2 ways to express the same onlu makes things more complex. Yeah, it might be confusing if `Permit all` doesn't do anything, or creates a Resource that can't be accessed if ([source](https://github.com/firezone/firezone/issues/2030#issuecomment-2093246090)).
- Potential implicit intent: missing_edge_case (heuristic; inferability=possible; relevance=possible).
- Later change evidence: verified=none; possible later-review commit=d1e562162f7982a435ae16db0a38fc64a9d70df9 (causal timing unverified).
- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain.
- Provisional suitability: B; reasons: POSSIBLE_BUT_UNVERIFIED_REVISION.

## [firezone/firezone#4569](https://github.com/firezone/firezone/pull/4569)

- Original task candidate: test(client): add reconnection tests from a client using a headless browser (current title, temporal availability unverified).
- Development history: opened 2024-04-10T03:14:28Z; 104 commits; 13 formal reviews; merged 2024-04-20T07:09:19Z.
- Chronological evidence:
  - 2024-04-10T03:14:28Z pr_opened by conectado: (no stable text) ([source](https://github.com/firezone/firezone/pull/4569)).
  - 2024-04-10T03:14:34Z issue_comment by vercel[bot]: [vc]: #aKLraB1WGQwS7C6j2MBlu1BoSsDomUfgORi8mVThStA=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0eXBlIjoiZ2l0aHViIiwicHJvamVjdHMiOlt7Im5hbWUiOiJmaXJlem9uZSIsImluc3BlY3RvclVybCI6 ([source](https://github.com/firezone/firezone/pull/4569#issuecomment-2046470687)).
  - 2024-04-10T03:16:16Z issue_comment by github-actions[bot]: #### Terraform Cloud Plan Output ``` Plan: 15 to add, 14 to change, 24 to destroy. ``` [Terraform Cloud Plan](https://app.terraform.io/app/firezone/workspaces/s ([source](https://github.com/firezone/firezone/pull/4569#issuecomment-2046471838)).
  - 2024-04-10T03:18:16Z review by jamilbk: This is great! Hopefully they're reliable. Minor suggestion to convert the JS to TS but I don't feel strongly. ([source](https://github.com/firezone/firezone/pull/4569#pullrequestreview-1990732898)).
  - 2024-04-10T03:19:34Z issue_comment by conectado: > This is great! Hopefully they're reliable. > > Minor suggestion to convert the JS to TS but I don't feel strongly. Yeah, I'd like to use typescript and set up ([source](https://github.com/firezone/firezone/pull/4569#issuecomment-2046473964)).
  - 2024-04-10T03:28:18Z issue_comment by github-actions[bot]: ### Performance Test Results #### TCP | Test Name | Received/s | Sent/s | Retransmits | |---|---|---|---| | direct-tcp-client2server | 243.1 MiB (-2%) | 245.2 M ([source](https://github.com/firezone/firezone/pull/4569#issuecomment-2046479505)).
  - 2024-04-10T18:39:20Z review by AndrewDryga: (no stable text) ([source](https://github.com/firezone/firezone/pull/4569#pullrequestreview-1992427162)).
  - 2024-04-10T18:39:20Z review_comment by AndrewDryga: This file is insane, gotta love javascript ([source](https://github.com/firezone/firezone/pull/4569#discussion_r1559906839)).
  - 2024-04-11T03:55:06Z review_comment by thomaseizinger: When is "later"? ([source](https://github.com/firezone/firezone/pull/4569#discussion_r1560403649)).
  - 2024-04-11T03:56:29Z review_comment by thomaseizinger: Why is this necessary? Doesn't the script exit by itself? ([source](https://github.com/firezone/firezone/pull/4569#discussion_r1560404315)).
  - 2024-04-11T03:57:10Z review_comment by thomaseizinger: Nit: Remove this newline. (Setting up browser and page seems to belong together). ([source](https://github.com/firezone/firezone/pull/4569#discussion_r1560404601)).
  - 2024-04-11T03:58:04Z review_comment by thomaseizinger: Let's make this fail if there is more than one page with the same URL. ([source](https://github.com/firezone/firezone/pull/4569#discussion_r1560405024)).
- Candidate cutoff: 2024-04-19T20:41:19Z, commit `8bfb9559e3b9c78ace1b70ce90b630f94a5a492a`; state evidence: prior_review_associated_commit.
- Explicit earlier requirements: This is great! Hopefully they're reliable. Minor suggestion to convert the JS to TS but I don't feel strongly. > This is great! Hopefully they're reliable. > > Minor suggestion to convert the JS to TS but I don't feel strongly. Yeah, I'd like to use typescript and set up a linter :) Just wanted to test if this was reproducible using puppeteer as quick as possible, which it was! I'd like to see an evaluation of Deno: https://docs.deno.com/ As far as I know, it is a batteries-included Typescript p
- Later human feedback: > Comp tests for DNS fail because we restart the relay using a different IP, thus not having any available relays (and the released versions do not yet parse the relays_presence message). The DNS restart test passes for this branch though! ~~Hm, why what that cause DNS to fail? That means that deploying this change will break everyone's DNS resources whenever we deploy, requiring them to restart their clients, correct (until they can upgrade their clients/gateways)? This can't go out until the m ([source](https://github.com/firezone/firezone/pull/4568#issuecomment-2067257394)).
- Potential implicit intent: bug_report (heuristic; inferability=possible; relevance=possible).
- Later change evidence: verified=none; possible later-review commit=6627dd09b8dd293bf4148aca6881affb0f1b8c65 (causal timing unverified).
- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain.
- Provisional suitability: B; reasons: POSSIBLE_BUT_UNVERIFIED_REVISION.

## [firezone/firezone#4746](https://github.com/firezone/firezone/pull/4746)

- Original task candidate: refactor: Make published artifact names consistent and use permalinks (current title, temporal availability unverified).
- Development history: opened 2024-04-22T21:46:48Z; 10 commits; 18 formal reviews; merged 2024-04-24T16:42:12Z.
- Chronological evidence:
  - 2024-04-22T21:46:48Z pr_opened by ReactorScram: (no stable text) ([source](https://github.com/firezone/firezone/pull/4746)).
  - 2024-04-22T21:46:54Z issue_comment by vercel[bot]: [vc]: #NiqI+j3l+ag+Drl+PU7V3NJjeiQ6ZyvwwuZdwjYwjCo=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0eXBlIjoiZ2l0aHViIiwicHJvamVjdHMiOlt7Im5hbWUiOiJmaXJlem9uZSIsImluc3BlY3RvclVybCI6 ([source](https://github.com/firezone/firezone/pull/4746#issuecomment-2071007426)).
  - 2024-04-22T21:48:43Z issue_comment by github-actions[bot]: #### Terraform Cloud Plan Output ``` Plan: 15 to add, 14 to change, 15 to destroy. ``` [Terraform Cloud Plan](https://app.terraform.io/app/firezone/workspaces/s ([source](https://github.com/firezone/firezone/pull/4746#issuecomment-2071009656)).
  - 2024-04-22T21:50:40Z review_comment by ReactorScram: Putting the OS name here is redundant since every package type (MSI, dmg, deb) belongs to exactly one OS, but I think it's easier to read "firezone-client-gui-w ([source](https://github.com/firezone/firezone/pull/4746#discussion_r1575394353)).
  - 2024-04-22T21:50:41Z review by ReactorScram: (no stable text) ([source](https://github.com/firezone/firezone/pull/4746#pullrequestreview-2015860559)).
  - 2024-04-22T21:56:48Z issue_comment by github-actions[bot]: ### Performance Test Results #### TCP | Test Name | Received/s | Sent/s | Retransmits | |---|---|---|---| | direct-tcp-client2server | 241.1 MiB (+0%) | 242.9 M ([source](https://github.com/firezone/firezone/pull/4746#issuecomment-2071019393)).
  - 2024-04-23T14:35:18Z review_comment by jamilbk: Makes sense ([source](https://github.com/firezone/firezone/pull/4746#discussion_r1576375212)).
  - 2024-04-23T14:53:32Z review by jamilbk: LGTM -- let's wait to merge until I have the website stuff in. Should I open a new PR or would you prefer I build off this one? ([source](https://github.com/firezone/firezone/pull/4746#pullrequestreview-2017458131)).
  - 2024-04-23T15:17:20Z review by jamilbk: (no stable text) ([source](https://github.com/firezone/firezone/pull/4746#pullrequestreview-2017574366)).
  - 2024-04-23T15:17:20Z review_comment by jamilbk: If we're changing these to `x86_64` we should probably do the gateway too right? ([source](https://github.com/firezone/firezone/pull/4746#discussion_r1576445603)).
  - 2024-04-23T15:20:07Z review by ReactorScram: (no stable text) ([source](https://github.com/firezone/firezone/pull/4746#pullrequestreview-2017581001)).
  - 2024-04-23T15:20:07Z review_comment by ReactorScram: Yeah. It feels a bit pointless to change to "x86_64" at all because I could definitely map "x86_64" to "x64" in the Rust code. I'm just doing it so that the upd ([source](https://github.com/firezone/firezone/pull/4746#discussion_r1576449806)).
- Candidate cutoff: 2024-04-23T19:00:22Z, commit `a9d945b028c231837c7f0811d373afec05cad3d6`; state evidence: prior_review_associated_commit.
- Explicit earlier requirements: LGTM -- let's wait to merge until I have the website stuff in. Should I open a new PR or would you prefer I build off this one? @jamilbk You can add the website commits to this PR, there shouldn't be any conflicts Let's change it then -- we'll soon have permalinks anyway Well, hmmm that'll require changing a bit of CI configuration. I'll see if I can do it in my commits. @ReactorScram This is ready for your review. I'll do a bit more testing, but this gives us permalinks that we can use for the
- Later human feedback: > @jamilbk But we've had all those `-pre` releases on Github, those would all alias to 1.0.0 under this system? Those won't work anyway because the package name is changing too right? The old download links will still work because we aren't editing past releases, so I'm not sure we need to burden this new system with the `pre` packages. ([source](https://github.com/firezone/firezone/pull/4746#issuecomment-2073207353)).
- Potential implicit intent: new_requirement (heuristic; inferability=possible; relevance=possible).
- Later change evidence: verified=none; possible later-review commit=none (causal timing unverified).
- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain.
- Provisional suitability: B; reasons: NO_VERIFIED_POST_FEEDBACK_REVISION.

## [superdb/zui#3076](https://github.com/superdb/zui/pull/3076)

- Original task candidate: Use zed query/describe endpoint (current title, temporal availability unverified).
- Development history: opened 2024-05-21T22:33:20Z; 1 commits; 12 formal reviews; merged 2024-06-03T19:16:29Z.
- Chronological evidence:
  - 2024-05-21T22:33:20Z pr_opened by mattnibs: (no stable text) ([source](https://github.com/superdb/zui/pull/3076)).
  - 2024-05-30T17:30:14Z issue_comment by philrz: I'm currently testing this branch at commit 6088bc5. I noticed something shown in the attached video: Large aggregation results now allow scrolling past the fir ([source](https://github.com/superdb/zui/pull/3076#issuecomment-2140393530)).
  - 2024-05-30T17:34:32Z issue_comment by philrz: This is effectively a note-to-self but I'll record it here in case anyone else has the same question upon reviewing these changes (cc: @jameskerr). In the ztest ([source](https://github.com/superdb/zui/pull/3076#issuecomment-2140407146)).
  - 2024-06-03T15:40:53Z review_comment by nwt: Nit: Maybe call this `describeQuery` for added clarity? ([source](https://github.com/superdb/zui/pull/3076#discussion_r1624680605)).
  - 2024-06-03T15:54:52Z review_comment by nwt: Doesn't the ability to paginate depend on whether output is sorted rather than whether it's an aggregation? ([source](https://github.com/superdb/zui/pull/3076#discussion_r1624699703)).
  - 2024-06-03T16:40:45Z review_comment by nwt: Nits: Every call to this passes `"test"` as `pool` so no need for a parameter. And `d` is a surprising name for the result of `fetchQueryInfo()`. ```suggestion  ([source](https://github.com/superdb/zui/pull/3076#discussion_r1624760742)).
  - 2024-06-03T16:41:37Z review_comment by nwt: Previously, all this stuff would happen regardless of the value of `info.error`. Why change that? ([source](https://github.com/superdb/zui/pull/3076#discussion_r1624761834)).
  - 2024-06-03T16:42:33Z review by nwt: (no stable text) ([source](https://github.com/superdb/zui/pull/3076#pullrequestreview-2094249306)).
  - 2024-06-03T17:13:12Z review by philrz: (no stable text) ([source](https://github.com/superdb/zui/pull/3076#pullrequestreview-2094454098)).
  - 2024-06-03T17:13:12Z review_comment by philrz: @nwt: I might be able to help field this one. As described in #2748 and https://github.com/brimdata/zed/issues/4491, it's my understanding that Zui's always tak ([source](https://github.com/superdb/zui/pull/3076#discussion_r1624802667)).
  - 2024-06-03T17:27:49Z review by nwt: (no stable text) ([source](https://github.com/superdb/zui/pull/3076#pullrequestreview-2094480331)).
  - 2024-06-03T17:27:49Z review_comment by nwt: @philrz: As I understand it, this pagination decision is about correctness rather than performance. The `summarize` operator produces output with nondeterminist ([source](https://github.com/superdb/zui/pull/3076#discussion_r1624819253)).
- Candidate cutoff: 2024-06-03T17:27:49Z, commit `3b4ce88ff7494d93c462a3a9f84791419d14fdd3`; state evidence: review_associated_commit.
- Explicit earlier requirements: This is effectively a note-to-self but I'll record it here in case anyone else has the same question upon reviewing these changes (cc: @jameskerr). In the ztest in https://github.com/brimdata/zed/pull/5126 I noticed that the `head` in the API call to `/describe` was being populated with the pool source info, but sniffing my API traffic in the Zui branch from this PR showed the `from` pool info going into `query` while `head` was `null`. I checked with @mattnibs and he confirmed that at this poin
- Later human feedback: @philrz: As I understand it, this pagination decision is about correctness rather than performance. The `summarize` operator produces output with nondeterministic order, so you can't paginate that output correctly by re-executing unless you sort it before applying `head` and `tail`. In fact, now that I've thought about it, I don't think we can paginate `summarize` output correctly unless it's sorted by all of the `summarize` keys. ([source](https://github.com/superdb/zui/pull/3076#discussion_r1624819253)).
- Potential implicit intent: new_constraint (heuristic; inferability=possible; relevance=possible).
- Later change evidence: verified=none; possible later-review commit=none (causal timing unverified).
- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain.
- Provisional suitability: B; reasons: NO_VERIFIED_POST_FEEDBACK_REVISION.

## [droidrun/mobilerun#217](https://github.com/droidrun/mobilerun/pull/217)

- Original task candidate: feat: add langfuse screenshot uploads and vision flag (current title, temporal availability unverified).
- Development history: opened 2025-11-25T07:46:01Z; 16 commits; 20 formal reviews; merged 2025-11-27T07:18:20Z.
- Chronological evidence:
  - 2025-11-25T07:46:01Z pr_opened by RasulOs: (no stable text) ([source](https://github.com/droidrun/mobilerun/pull/217)).
  - 2025-11-26T08:28:01Z review_comment by johnmalek312: this would break in cloud when running multiple agents in parallel. ideally you would remove this entirely. langfuse_screenshots_enabled too ([source](https://github.com/droidrun/mobilerun/pull/217#discussion_r2563935940)).
  - 2025-11-26T08:30:53Z review_comment by johnmalek312: we have a function for image upload that goes to gcp bucket ```_upload_media_to_langfuse`` isntead of uploading baase64 to the trace ([source](https://github.com/droidrun/mobilerun/pull/217#discussion_r2563948678)).
  - 2025-11-26T08:31:14Z review_comment by johnmalek312: this isnt needed if you attach the image to an existing span, overcomplicates it ([source](https://github.com/droidrun/mobilerun/pull/217#discussion_r2563950402)).
  - 2025-11-26T08:31:46Z review_comment by johnmalek312: same here ([source](https://github.com/droidrun/mobilerun/pull/217#discussion_r2563953122)).
  - 2025-11-26T08:42:44Z review by sleynsol: I see that you always call "record_langfuse_screenshot" after an ScreenshotEvent is written to the event stream. The Screenshots event gets passed up to the Dro ([source](https://github.com/droidrun/mobilerun/pull/217#pullrequestreview-3509730312)).
  - 2025-11-26T09:26:51Z review by johnmalek312: (no stable text) ([source](https://github.com/droidrun/mobilerun/pull/217#pullrequestreview-3509654024)).
  - 2025-11-26T09:35:54Z issue_comment by johnmalek312: langfuse processor has access to the agent, you can use `agent.shared_state.screenshot` which contains last screenshot, but this is only used in manager and exe ([source](https://github.com/droidrun/mobilerun/pull/217#issuecomment-3580444604)).
  - 2025-11-26T11:17:23Z review by RasulOs: (no stable text) ([source](https://github.com/droidrun/mobilerun/pull/217#pullrequestreview-3510430188)).
  - 2025-11-26T11:17:23Z review_comment by RasulOs: Need to save the last span instead of root, checked both options, this is better ([source](https://github.com/droidrun/mobilerun/pull/217#discussion_r2564583251)).
  - 2025-11-26T11:17:33Z review_comment by RasulOs: Same as above ([source](https://github.com/droidrun/mobilerun/pull/217#discussion_r2564583738)).
  - 2025-11-26T11:17:34Z review by RasulOs: (no stable text) ([source](https://github.com/droidrun/mobilerun/pull/217#pullrequestreview-3510430708)).
- Candidate cutoff: 2025-11-26T09:35:54Z, commit `d8d005fbd0a6e8b8545c4a1c61dddcef3df4f0ce`; state evidence: prior_review_associated_commit.
- Explicit earlier requirements: I see that you always call "record_langfuse_screenshot" after an ScreenshotEvent is written to the event stream. The Screenshots event gets passed up to the DroidAgent where it's handled inside the function "handle_stream_event" Isn't it possible to just call the "record_langfuse_screenshot" here instead of doing it everywhere where the screenshot event is already thrown?
- Later human feedback: langfuse processor has access to the agent, you can use `agent.shared_state.screenshot` which contains last screenshot, but this is only used in manager and executor agent, will need to set the screenshot in codeact agent. then you can upload the screenshot and attach it to CodeActAgent.handle_llm_input and ManagerAgent.get_response. So you would only need to modify codeact agent to save screenshot to the `shared_state` and then use it in langfuse_processor ([source](https://github.com/droidrun/mobilerun/pull/217#issuecomment-3580444604)).
- Potential implicit intent: new_constraint (heuristic; inferability=possible; relevance=possible).
- Later change evidence: verified=none; possible later-review commit=287551105da56262c58f148d3c06b63918e0c521 (causal timing unverified).
- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain.
- Provisional suitability: B; reasons: POSSIBLE_BUT_UNVERIFIED_REVISION.

## [firezone/firezone#6403](https://github.com/firezone/firezone/pull/6403)

- Original task candidate: feat(gateway): allow out-of-order `allow_access` requests (current title, temporal availability unverified).
- Development history: opened 2024-08-22T05:47:37Z; 7 commits; 21 formal reviews; merged 2024-08-28T13:27:00Z.
- Chronological evidence:
  - 2024-08-22T05:47:37Z pr_opened by thomaseizinger: (no stable text) ([source](https://github.com/firezone/firezone/pull/6403)).
  - 2024-08-22T05:47:40Z issue_comment by vercel[bot]: [vc]: #XSoV4t/qJIL/fx56HAbsaI+t1OCrB87qjCItWoX7iFk=:eyJpc01vbm9yZXBvIjp0cnVlLCJ0eXBlIjoiZ2l0aHViIiwicHJvamVjdHMiOlt7Im5hbWUiOiJmaXJlem9uZSIsImluc3BlY3RvclVybCI6 ([source](https://github.com/firezone/firezone/pull/6403#issuecomment-2303834774)).
  - 2024-08-22T05:48:06Z review by thomaseizinger: (no stable text) ([source](https://github.com/firezone/firezone/pull/6403#pullrequestreview-2253549289)).
  - 2024-08-22T05:48:06Z review_comment by thomaseizinger: @AndrewDryga I simply copied the behaviour from the `request_connection` flow here. ([source](https://github.com/firezone/firezone/pull/6403#discussion_r1726377454)).
  - 2024-08-22T06:02:43Z issue_comment by thomaseizinger: Whilst building this, I had an idea for how we could optimise connection setup latency: https://github.com/firezone/firezone/issues/6404 ([source](https://github.com/firezone/firezone/pull/6403#issuecomment-2303850556)).
  - 2024-08-22T06:04:36Z review by thomaseizinger: (no stable text) ([source](https://github.com/firezone/firezone/pull/6403#pullrequestreview-2253569692)).
  - 2024-08-22T06:04:36Z review_comment by thomaseizinger: This is backwards-compatible because old gateways will simply ignore this field and we don't remove any existing ones. ([source](https://github.com/firezone/firezone/pull/6403#discussion_r1726395144)).
  - 2024-08-22T17:45:36Z review_comment by jamilbk: ```suggestion client = Clients.fetch_client_by_id!(client_id) ``` I don't think you need the send the associated actor to the Gateway right? ([source](https://github.com/firezone/firezone/pull/6403#discussion_r1727567713)).
  - 2024-08-22T17:49:09Z review_comment by jamilbk: Hm I may be missing something, but where are you pulling these out of the `client` in the message sent by the portal? ``` client: client ``` AFAIK with the abov ([source](https://github.com/firezone/firezone/pull/6403#discussion_r1727573695)).
  - 2024-08-22T17:50:04Z review by jamilbk: (no stable text) ([source](https://github.com/firezone/firezone/pull/6403#pullrequestreview-2255279249)).
  - 2024-08-22T19:44:17Z review by conectado: (no stable text) ([source](https://github.com/firezone/firezone/pull/6403#pullrequestreview-2255512762)).
  - 2024-08-22T19:44:17Z review_comment by conectado: Those are already extracted in the eventloop ([source](https://github.com/firezone/firezone/pull/6403#discussion_r1727719925)).
- Candidate cutoff: 2024-08-26T15:40:22Z, commit `08c90c4f84e301f0b588c40e5f98c9bf58275e89`; state evidence: review_associated_commit.
- Explicit earlier requirements: @AndrewDryga I simply copied the behaviour from the `request_connection` flow here. Whilst building this, I had an idea for how we could optimise connection setup latency: https://github.com/firezone/firezone/issues/6404 This is backwards-compatible because old gateways will simply ignore this field and we don't remove any existing ones. Those are already extracted in the eventloop [here](https://github.com/firezone/firezone/pull/6403/files#diff-242d43c4a7a93d0fbd3f84f8af923dbd1ff6d40137ead68342
- Later human feedback: @thomaseizinger this looks good, all we need is to check in tests that this field is present (you can also copy that part from the other test), just to make sure we won't break this in future. ([source](https://github.com/firezone/firezone/pull/6403#discussion_r1731438721)).
- Potential implicit intent: new_requirement (heuristic; inferability=possible; relevance=possible).
- Later change evidence: verified=none; possible later-review commit=none (causal timing unverified).
- Cutoff state: recoverable by commit SHA; exact pre-review visibility may be uncertain.
- Provisional suitability: B; reasons: NO_VERIFIED_POST_FEEDBACK_REVISION.
