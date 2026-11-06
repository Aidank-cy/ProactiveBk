# Release policy for repository candidates

The discovery has two research processing tracks after numeric filtering. Both can be represented in the same downstream research schema and analyzed with the same methods. The current project stops at repository discovery; it has not downloaded repository source or collected PR trajectories for these candidates.

| Track | Current count | Local record | Public release gate |
|---|---:|---|---|
| GitHub-detected SPDX license marked OSI-approved | 318 | `results/qualified_repositories.csv` | Review and comply with each repository's actual license terms, notices, attribution, and applicable contribution licenses before publishing code or derived materials. |
| License status unverified (`NOASSERTION` or no detected license) | 44 | `results/restricted/repositories.csv` | Hold repository-level research outputs locally. Publish code, derived benchmark instances, trajectories, or datasets only after verifying an applicable license or obtaining written permission covering the intended uses. |

`results/processing_candidates.csv` combines the two tracks for local planning and records `processing_track`, `authorization_status`, `authorization_evidence_url`, and `publication_gate` on each row. Restricted records, the complete candidate inventory, excluded records, and pending records are gitignored. The public files are `results/qualified_repositories.csv`, aggregate stage and date counts, `results/summary_statistics.json`, this policy, and the report.

GitHub's `NOASSERTION` and missing license detection mean that the automated check could not confirm a license. They do not prove that no license exists. Organization ownership, public visibility, and non-profit research status are not substitutes for a license or other applicable permission. Before copying, changing, or distributing code from the restricted track, review the relevant rights with the research institution's legal or research compliance team.

An earlier public commit of this repository included the 44 repositories' metadata in `all_candidates.csv` and `pending_repositories.csv`. The current public branch removes those files, but Git history or copies may still contain them. No restricted code or PR trajectories have been published by this discovery project.
