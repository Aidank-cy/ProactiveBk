# Dataset change log: semantic repair

Every controlled addition is also recorded beside its initial record or event in the reconstruction documents, with source paths and affected fixed Tasks. No evaluation model produced these changes.

| Scenario | Earlier data | Repair and GT effect |
|---|---|---|
| Rental | Weekend-only east-gate detour incorrectly invalidated long-term commute; calendar conflicts omitted; contract Task read as early checklist. | Explicit post-start daily commute criterion, visible calendar extract, temporary 51-minute detour separate from 38-minute daily route; T1 remains Ready until viewing window ends. T4 explicitly requires the final attachment package. North quote and slot supplements are explained. |
| Travel | 3180-dollar quote reused for days, hotel sold out despite final stay, August 17 arrival contradicted August 16 receipts, holds conflated with payments. | Quote and seat guarantee expires August 1 at 00:55; flight becomes Ready only in the valid quote window. User externally books hotel before public sellout and confirms 1480-dollar airfare August 11. Actual arrival aligns to August 16 receipts. Bank hold, declined charge, settlement and release request remain distinct. |
| Shopping | 163.40 was called the optimal cart; Memory asked optimization; old sale time and platform intervention application remained actionable after they expired or completed. | Mall rules are exposed as raw facts; deterministic enumeration gives A-standard/B-single/C-single at 146.30. Optimization answer is removed from Memory and Event. Sale time expires and user externally submits platform intervention; specific authorization updates Memory. |
| Team building | Notice time leaked future 09:00 detail; one bus driver verified; risky paid reservation called cancellable; final archive omitted factory/PPE status. | Notice time appears only in final visitor email. Both drivers, vehicles and accommodations are stated. User-authorized zero-deposit temporary hold has a deadline while personal payment risk remains. Final task is a dated status-and-missing-evidence package. |

## Key event and GT comparison

Stage IDs after an inserted event are intentionally renumbered; compare event content and timestamps when reviewing the old and new JSON.

| Scenario | Earlier key label/content | Repaired key label/content |
|---|---|---|
| Rental | S14 weekend east-gate 51 minutes made rental_t1 commute Unsatisfied and removed it from Ready. | S14 distinguishes temporary viewing-weekend detour from post-start daily 38-minute route; rental_t1 remains Ready. Both viewing Tasks leave Ready when their dated slots pass at S15. |
| Travel | S07 3180-dollar airfare immediately marked budget Satisfied and stayed Ready across ten days. | S07 airfare budget Unknown; S08 exposes lodging and cost bounds while the quote is valid, making travel_t1 Ready. S09 simulated time passes the fare cutoff and t1 leaves Ready; hotel budget becomes Unknown until external booking removes the reservation Task. |
| Travel | August 17 arrival and August 16 receipts coexisted; hotel showed sold out before a later stay bill; holds and settlement were mixed. | A dated user external booking precedes public stock zero, external ticket confirmation precedes travel, and actual island arrival is August 16. The bank hold, 24-dollar decline, August 11 settlement, and hotel release request each have separate Event facts and Memory GT. |
| Shopping | S07 Event and Memory GT asserted A-economy/B-single/C-three-pack at 163.40 was optimal; S15 sale plan kept Ready after July 6 17:00. | S07 exposes only SKU and coupon inputs. Independent 18-combination enumeration yields A-standard/B-single/C-single at 146.30 in hidden audit. Sale time expires before the July 8 Stage; intervention application is marked externally submitted before approval. |
| Team building | S11 Memory GT already gave 09:00 safety briefing, and S15 marked a costly reservation Ready despite personal-account risk. | S11 says briefing time Unknown; S16 visitor notice gives 09:00 and special handling. Only the zero-deposit, loss-free temporary hold becomes Ready at S16; its offer expires before the next Stage. |

Automated tests check provenance structure, time cutoffs and generated consistency. Researchers must still adjudicate controlled supplements and unresolved business ambiguities before scored model inference.
