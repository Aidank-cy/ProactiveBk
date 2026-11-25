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

## Final pilot fact and matching repair

This pass corrects reference answers and recognition criteria without changing the four fixed scenarios, 19 tasks, or event counts. The hotel-date correction moves one condition transition from Travel S04 to S08; first Ready stages remain unchanged.

| Scenario and field | Earlier GT or rule | Repaired GT or rule |
|---|---|---|
| Travel S04 `t_hotel_dates` | Full August 16–23 stay and seven nights before the hotel dates were visible. | Only August 16 evening arrival advice is known; full dates first appear with the S08 hotel offer. Evidence changes from e004 to e008 for the full dates. |
| Travel S06 `t_flight_stock` | Every segment has at least three seats. | Some segments have three seats; availability of two seats on every leg remains Unknown until S07 confirms two seats. |
| Travel S17 `t_flight_hold` | Airline seat hold lasts 72 hours. | Airline temporarily holds two seats but gives no hold expiry; 72 hours is the bank payment-confirmation deadline. |
| Travel S20 `t_claim_payment` | $70 transfer marked paid after service use. | Service used, payment unconfirmed until S22 receipt states $70 settled. |
| Travel `travel_t4` | Seasickness preference was in context but lacked its own Memory question. | `t_land_comfort` asks for Xu Wen's seasickness and long-speedboat limit, grounded in h002 and required by the task. |
| Team S00–S14 `b_notice_goal` | Claimed a July 18 second authorization before it occurred. | Only July 1 permission to prepare internal drafts, grounded in h002; S15 update uses e015. |
| Team S06–S07 `b_lunch_quote` | S06 prematurely stated the 11880-yuan offer; S07 asserted unsupported 70-person capacity. | S06 records settlement rule while price and capacity are unknown; S07 states 11880 yuan and confirmed accommodation of 44 people. |
| All 19 Matching Guidelines | Some demanded a complete plan or exact SKU, coupon, price and reference wording. | Recognition of the specified actionable user goal is enough; output need not solve the task. Wrong object, violated constraints or unauthorized execution remain non-matches. |

Automated tests check provenance structure, time cutoffs and generated consistency. Researchers must still adjudicate controlled supplements and unresolved business ambiguities before scored model inference.
