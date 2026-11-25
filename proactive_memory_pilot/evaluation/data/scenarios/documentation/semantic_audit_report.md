# Semantic audit report

Each row refers to a reviewer-only `*_semantic_audit.json` file. Those files give every Memory answer and visible-record evidence, condition-to-question mapping, time cutoff, Ready support, and missing fact. This trace supports manual review; it does not prove the business truth of a controlled addition.

## rental

| Stage | Event | Simulated time | Active goals | Changed facts | Changed conditions | Ready | New | Leaving | Ready evidence | Unknown conditions |
|---|---|---|---|---|---|---|---|---|---|---:|
| s00 | — | 2026-07-10T09:00:00+08:00 | rental_t1, rental_t2, rental_t3 | ∅ | ∅ | ∅ | ∅ | ∅ | ∅ | 18 |
| s01 | e001 | 2026-07-17T09:00:00+08:00 | rental_t1, rental_t2, rental_t3 | ∅ | ∅ | ∅ | ∅ | ∅ | ∅ | 18 |
| s02 | e002 | 2026-07-20T09:00:00+08:00 | rental_t1, rental_t2, rental_t3 | r_c_commute | rental_t1 | ∅ | ∅ | ∅ | ∅ | 17 |
| s03 | e003 | 2026-07-22T09:00:00+08:00 | rental_t1, rental_t2, rental_t3 | r_c_reg | rental_t1, rental_t4 | ∅ | ∅ | ∅ | ∅ | 17 |
| s04 | e004 | 2026-07-23T11:00:00+08:00 | rental_t1, rental_t2, rental_t3 | r_c_reg, r_c_slot, r_c_status | rental_t1, rental_t4 | rental_t1 | rental_t1 | ∅ | e002, e004, h003, h004, h005 | 14 |
| s05 | e005 | 2026-07-24T09:00:00+08:00 | rental_t1, rental_t2, rental_t3 | r_b_price | rental_t3 | rental_t1 | ∅ | ∅ | e002, e004, h003, h004, h005 | 14 |
| s06 | e006 | 2026-07-25T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_contract_goal, r_contract_status | rental_t4 | rental_t1 | ∅ | ∅ | e002, e004, h003, h004, h005 | 11 |
| s07 | e007 | 2026-07-27T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_calendar | ∅ | rental_t1 | ∅ | ∅ | e002, e004, e007, h003, h005 | 11 |
| s08 | e008 | 2026-07-28T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_b_risk | rental_t3 | rental_t1 | ∅ | ∅ | e002, e004, e007, h003, h005 | 10 |
| s09 | e009 | 2026-07-30T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_a_commute | rental_t2 | rental_t1 | ∅ | ∅ | e002, e004, e007, h003, h005 | 9 |
| s10 | e010 | 2026-08-01T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_contract_owner, r_contract_deposit, r_contract_repair, r_contract_fee | rental_t4 | rental_t1 | ∅ | ∅ | e002, e004, e007, h003, h005 | 9 |
| s11 | e011 | 2026-08-02T11:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_a_price, r_a_reg, r_a_slot | rental_t2 | rental_t1, rental_t2 | rental_t2 | ∅ | e002, e004, e007, e009, e011, h003, h005 | 7 |
| s12 | e012 | 2026-08-03T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_b_risk | ∅ | rental_t1, rental_t2 | ∅ | ∅ | e002, e004, e007, e009, e011, h003, h005 | 7 |
| s13 | e013 | 2026-08-05T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | ∅ | ∅ | rental_t1, rental_t2 | ∅ | ∅ | e002, e004, e007, e009, e011, h003, h005 | 7 |
| s14 | e014 | 2026-08-06T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_c_commute | ∅ | rental_t1, rental_t2 | ∅ | ∅ | e004, e007, e009, e011, e014, h003, h005 | 7 |
| s15 | e015 | 2026-08-10T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_c_slot, r_a_slot, r_b_slot, r_c_commute | rental_t1, rental_t2, rental_t3 | ∅ | ∅ | rental_t1, rental_t2 | ∅ | 6 |
| s16 | e016 | 2026-08-11T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_contract_owner, r_contract_deposit, r_contract_repair, r_contract_fee | rental_t4 | ∅ | ∅ | ∅ | ∅ | 3 |
| s17 | e017 | 2026-08-12T11:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | r_contract_fee, r_contract_status | rental_t4 | rental_t4 | rental_t4 | ∅ | e004, e006, e016, e017, h005 | 2 |
| s18 | e018 | 2026-08-14T09:00:00+08:00 | rental_t1, rental_t2, rental_t3, rental_t4 | ∅ | ∅ | rental_t4 | ∅ | ∅ | e004, e006, e016, e017, h005 | 2 |

### Task transition audit

- `rental_t1`: preceding s03; first Ready s04; Ready at s04, s05, s06, s07, s08, s09, s10, s11, s12, s13, s14; leaves at s15.
- `rental_t2`: preceding s10; first Ready s11; Ready at s11, s12, s13, s14; leaves at s15.
- `rental_t3`: never Ready; see Unknown and Unsatisfied condition evidence in the JSON audit.
- `rental_t4`: preceding s16; first Ready s17; Ready at s17, s18; leaves at —.

## travel

| Stage | Event | Simulated time | Active goals | Changed facts | Changed conditions | Ready | New | Leaving | Ready evidence | Unknown conditions |
|---|---|---|---|---|---|---|---|---|---|---:|
| s00 | — | 2026-07-24T09:25:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | ∅ | ∅ | ∅ | ∅ | ∅ | ∅ | 26 |
| s01 | e001 | 2026-07-25T11:30:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_deadline, t_transfer_route | travel_t3 | ∅ | ∅ | ∅ | ∅ | 24 |
| s02 | e002 | 2026-07-26T20:05:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_dates | ∅ | ∅ | ∅ | ∅ | ∅ | 24 |
| s03 | e003 | 2026-07-27T09:20:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_visa | travel_t1 | ∅ | ∅ | ∅ | ∅ | 23 |
| s04 | e004 | 2026-07-27T10:00:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_hotel_dates | travel_t2 | ∅ | ∅ | ∅ | ∅ | 22 |
| s05 | e005 | 2026-07-28T13:05:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_budget | ∅ | ∅ | ∅ | ∅ | ∅ | 22 |
| s06 | e006 | 2026-07-30T10:15:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_flight_stock, t_flight_time, t_flight_hold | travel_t1, travel_t3 | ∅ | ∅ | ∅ | ∅ | 18 |
| s07 | e007 | 2026-07-31T18:55:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_flight_stock, t_flight_ticket, t_flight_price, t_flight_hold | travel_t1, travel_t2 | ∅ | ∅ | ∅ | ∅ | 17 |
| s08 | e008 | 2026-07-31T19:10:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_hotel_stock, t_hotel_place, t_hotel_price, t_hotel_cancel | travel_t1, travel_t2 | travel_t1, travel_t2 | travel_t1, travel_t2 | ∅ | e001, e002, e003, e004, e005, e006, e007, e008, h001, h002 | 12 |
| s09 | e009 | 2026-08-01T11:00:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_flight_stock, t_flight_price, t_flight_hold, t_flight_open | travel_t1, travel_t2 | ∅ | ∅ | travel_t1, travel_t2 | ∅ | 16 |
| s10 | e010 | 2026-08-02T18:00:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | ∅ | ∅ | ∅ | ∅ | ∅ | ∅ | 16 |
| s11 | e011 | 2026-08-02T20:00:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_hotel_open, t_hotel_stock | travel_t2 | ∅ | ∅ | ∅ | ∅ | 17 |
| s12 | e012 | 2026-08-03T10:00:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_hotel_stock, t_hotel_open | travel_t2 | ∅ | ∅ | ∅ | ∅ | 16 |
| s13 | e013 | 2026-08-04T21:00:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t5 | t_claim_policy, t_auth | travel_t5 | ∅ | ∅ | ∅ | ∅ | 15 |
| s14 | e014 | 2026-08-06T13:00:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t4, travel_t5 | t_land_goal, t_land_time, t_land_weather, t_land_open | travel_t4 | ∅ | ∅ | ∅ | ∅ | 10 |
| s15 | e015 | 2026-08-07T11:05:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t4, travel_t5 | t_land_option, t_land_weather | travel_t4 | travel_t4 | travel_t4 | ∅ | e014, e015, h001, h002 | 9 |
| s16 | e016 | 2026-08-08T16:45:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t4, travel_t5 | t_transfer_vendor, t_transfer_cost | travel_t3 | travel_t3, travel_t4 | travel_t3 | ∅ | e001, e006, e013, e014, e015, e016, h001, h002 | 7 |
| s17 | e017 | 2026-08-10T22:30:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t4, travel_t5 | t_flight_open, t_flight_price, t_flight_hold, t_hotel_open, t_claim_payment | travel_t1 | travel_t3, travel_t4 | ∅ | ∅ | e001, e006, e013, e014, e015, e016, h001, h002 | 7 |
| s18 | e018 | 2026-08-11T13:00:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t4, travel_t5 | t_flight_open, t_flight_hold, t_claim_payment | ∅ | travel_t3, travel_t4 | ∅ | ∅ | e001, e006, e013, e014, e015, e016, h001, h002 | 7 |
| s19 | e019 | 2026-08-14T17:35:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t4, travel_t5 | t_flight_open, t_flight_time | travel_t1, travel_t3 | travel_t4 | ∅ | travel_t3 | e014, e015, h001, h002 | 9 |
| s20 | e020 | 2026-08-16T15:30:00-06:00 | travel_t1, travel_t2, travel_t3, travel_t4, travel_t5 | t_flight_time, t_transfer_open, t_transfer_vendor, t_hotel_cancel, t_claim_payment | travel_t2, travel_t3 | travel_t4 | ∅ | ∅ | e014, e015, h001, h002 | 9 |
| s21 | e021 | 2026-08-20T09:00:00-06:00 | travel_t1, travel_t2, travel_t3, travel_t4, travel_t5 | t_land_open, t_land_weather | travel_t4 | ∅ | ∅ | travel_t4 | ∅ | 10 |
| s22 | e022 | 2026-08-24T12:00:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t4, travel_t5 | t_claim_payment, t_claim_receipts, t_hotel_price, t_hotel_open | travel_t5 | ∅ | ∅ | ∅ | ∅ | 9 |
| s23 | e023 | 2026-08-25T13:30:00+08:00 | travel_t1, travel_t2, travel_t3, travel_t4, travel_t5 | t_claim_return, t_claim_receipts | travel_t5 | travel_t5 | travel_t5 | ∅ | e013, e022, e023, h001, h002 | 7 |

### Task transition audit

- `travel_t1`: preceding s07; first Ready s08; Ready at s08; leaves at s09.
- `travel_t2`: preceding s07; first Ready s08; Ready at s08; leaves at s09.
- `travel_t3`: preceding s15; first Ready s16; Ready at s16, s17, s18; leaves at s19.
- `travel_t4`: preceding s14; first Ready s15; Ready at s15, s16, s17, s18, s19, s20; leaves at s21.
- `travel_t5`: preceding s22; first Ready s23; Ready at s23; leaves at —.

## shopping

| Stage | Event | Simulated time | Active goals | Changed facts | Changed conditions | Ready | New | Leaving | Ready evidence | Unknown conditions |
|---|---|---|---|---|---|---|---|---|---|---:|
| s00 | — | 2026-06-15T09:00:00+08:00 | shopping_t2, shopping_t4 | ∅ | ∅ | ∅ | ∅ | ∅ | ∅ | 30 |
| s01 | e001 | 2026-06-16T10:00:00+08:00 | shopping_t2, shopping_t4 | ∅ | ∅ | ∅ | ∅ | ∅ | ∅ | 30 |
| s02 | e002 | 2026-06-17T14:05:00+08:00 | shopping_t2, shopping_t4 | s_ref_case | shopping_t1 | ∅ | ∅ | ∅ | ∅ | 29 |
| s03 | e003 | 2026-06-18T18:20:00+08:00 | shopping_t2, shopping_t4 | ∅ | ∅ | ∅ | ∅ | ∅ | ∅ | 29 |
| s04 | e004 | 2026-06-20T11:20:00+08:00 | shopping_t2, shopping_t3, shopping_t4 | s_card_goal, s_card_pair | shopping_t3 | ∅ | ∅ | ∅ | ∅ | 26 |
| s05 | e005 | 2026-06-21T15:05:00+08:00 | shopping_t2, shopping_t3, shopping_t4 | s_sale_buyer | shopping_t2 | ∅ | ∅ | ∅ | ∅ | 25 |
| s06 | e006 | 2026-06-22T15:00:00+08:00 | shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_cart_goal, s_cart_status | shopping_t5 | ∅ | ∅ | ∅ | ∅ | 22 |
| s07 | e007 | 2026-06-23T13:05:00+08:00 | shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_ref_case, s_cart_catalog, s_cart_stock, s_cart_coupon | shopping_t1, shopping_t5 | shopping_t5 | shopping_t5 | ∅ | e006, e007, h002 | 18 |
| s08 | e008 | 2026-06-24T09:05:00+08:00 | shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_card_pair | shopping_t3 | shopping_t5 | ∅ | ∅ | e006, e007, h002 | 17 |
| s09 | e009 | 2026-06-25T10:00:00+08:00 | shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_stroller_policy, s_stroller_cost | shopping_t4 | shopping_t5 | ∅ | ∅ | e006, e007, h002 | 15 |
| s10 | e010 | 2026-06-26T16:20:00+08:00 | shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_sale_platform, s_card_order, s_card_docs | shopping_t2, shopping_t3 | shopping_t3, shopping_t5 | shopping_t3 | ∅ | e004, e006, e007, e008, e010, h002 | 12 |
| s11 | e011 | 2026-06-30T10:05:00+08:00 | shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_card_status | shopping_t3 | shopping_t5 | ∅ | shopping_t3 | e006, e007, h002 | 12 |
| s12 | e012 | 2026-07-02T09:00:00+08:00 | shopping_t1, shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_ref_goal, s_ref_rule, s_ref_photo, s_ref_video, s_ref_open, s_auth | shopping_t1 | shopping_t5 | ∅ | ∅ | e006, e007, e012 | 6 |
| s13 | e013 | 2026-07-04T10:00:00+08:00 | shopping_t1, shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_ref_video, s_stroller_batch, s_stroller_policy, s_stroller_cost, s_stroller_travel, s_stroller_open | shopping_t1, shopping_t4 | shopping_t1, shopping_t4, shopping_t5 | shopping_t1, shopping_t4 | ∅ | e006, e007, e012, e013, h002 | 3 |
| s14 | e014 | 2026-07-06T14:00:00+08:00 | shopping_t1, shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_sale_price, s_sale_time, s_sale_platform, s_sale_choice, s_sale_buyer | shopping_t2 | shopping_t1, shopping_t2, shopping_t4, shopping_t5 | shopping_t2 | ∅ | e006, e007, e012, e013, e014, h001, h002 | 0 |
| s15 | e015 | 2026-07-08T18:05:00+08:00 | shopping_t1, shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_card_status, s_sale_time, s_sale_open | ∅ | shopping_t1, shopping_t4, shopping_t5 | ∅ | shopping_t2 | e006, e007, e012, e013, h002 | 0 |
| s16 | e016 | 2026-07-09T08:30:00+08:00 | shopping_t1, shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_ref_case, s_ref_open | shopping_t1 | shopping_t4, shopping_t5 | ∅ | shopping_t1 | e006, e007, e012, e013, h002 | 0 |
| s17 | e017 | 2026-07-10T11:05:00+08:00 | shopping_t1, shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_ref_case, s_ref_open | shopping_t1 | shopping_t4, shopping_t5 | ∅ | ∅ | e006, e007, e012, e013, h002 | 0 |
| s18 | e018 | 2026-07-11T16:05:00+08:00 | shopping_t1, shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_sale_listing, s_sale_open | shopping_t2 | shopping_t4, shopping_t5 | ∅ | ∅ | e006, e007, e012, e013, h002 | 0 |
| s19 | e019 | 2026-07-14T10:00:00+08:00 | shopping_t1, shopping_t2, shopping_t3, shopping_t4, shopping_t5 | s_stroller_cost, s_stroller_open | ∅ | shopping_t5 | ∅ | shopping_t4 | e006, e007, e012 | 0 |

### Task transition audit

- `shopping_t1`: preceding s12; first Ready s13; Ready at s13, s14, s15; leaves at s16.
- `shopping_t2`: preceding s13; first Ready s14; Ready at s14; leaves at s15.
- `shopping_t3`: preceding s09; first Ready s10; Ready at s10; leaves at s11.
- `shopping_t4`: preceding s12; first Ready s13; Ready at s13, s14, s15, s16, s17, s18; leaves at s19.
- `shopping_t5`: preceding s06; first Ready s07; Ready at s07, s08, s09, s10, s11, s12, s13, s14, s15, s16, s17, s18, s19; leaves at —.

## team_building

| Stage | Event | Simulated time | Active goals | Changed facts | Changed conditions | Ready | New | Leaving | Ready evidence | Unknown conditions |
|---|---|---|---|---|---|---|---|---|---|---:|
| s00 | — | 2026-07-01T09:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | ∅ | ∅ | ∅ | ∅ | ∅ | ∅ | 33 |
| s01 | e001 | 2026-07-02T10:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | ∅ | ∅ | ∅ | ∅ | ∅ | ∅ | 33 |
| s02 | e002 | 2026-07-03T11:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_finance_rule, b_bus_invoice | team_t5 | ∅ | ∅ | ∅ | ∅ | 32 |
| s03 | e003 | 2026-07-04T09:30:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_count, b_factory_needs | team_t1, team_t3, team_t4 | ∅ | ∅ | ∅ | ∅ | 32 |
| s04 | e004 | 2026-07-05T14:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_factory_stock, b_factory_ppe, b_factory_quote | team_t1 | ∅ | ∅ | ∅ | ∅ | 31 |
| s05 | e005 | 2026-07-07T15:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | ∅ | ∅ | ∅ | ∅ | ∅ | ∅ | 31 |
| s06 | e006 | 2026-07-08T10:30:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_factory_cancel, b_lunch_quote | team_t1 | ∅ | ∅ | ∅ | ∅ | 31 |
| s07 | e007 | 2026-07-09T09:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_lunch_menu, b_lunch_invoice, b_lunch_time, b_lunch_quote, b_factory_quote | team_t3 | ∅ | ∅ | ∅ | ∅ | 26 |
| s08 | e008 | 2026-07-10T16:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_count, b_bus_quote, b_bus_invoice, b_factory_quote | team_t1, team_t2, team_t3 | team_t3 | team_t3 | ∅ | e003, e007, e008, h002 | 18 |
| s09 | e009 | 2026-07-11T09:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_factory_ppe | team_t1 | team_t3 | ∅ | ∅ | e003, e007, e008, h002 | 17 |
| s10 | e010 | 2026-07-12T10:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_notice_rules | team_t4 | team_t3 | ∅ | ∅ | e003, e007, e008, h002 | 17 |
| s11 | e011 | 2026-07-13T11:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_bus_driver, b_bus_needs, b_bus_schedule, b_notice_time, b_notice_route | team_t2, team_t4 | team_t2, team_t3 | team_t2 | ∅ | e003, e007, e008, e011, h002 | 13 |
| s12 | e012 | 2026-07-14T09:30:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_factory_stock, b_factory_security, b_factory_open | team_t1 | team_t2, team_t3 | ∅ | ∅ | e003, e007, e008, e011, h002 | 12 |
| s13 | e013 | 2026-07-16T10:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | ∅ | ∅ | team_t2, team_t3 | ∅ | ∅ | e003, e007, e008, e011, h002 | 12 |
| s14 | e014 | 2026-07-17T15:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | ∅ | ∅ | team_t2, team_t3 | ∅ | ∅ | e003, e007, e008, e011, h002 | 12 |
| s15 | e015 | 2026-07-18T09:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_factory_stock, b_factory_security, b_factory_ppe, b_factory_open, b_factory_cancel, b_factory_hold, b_auth, b_notice_goal, b_notice_open | team_t1, team_t4 | team_t2, team_t3 | ∅ | ∅ | e003, e007, e008, e011, h002 | 9 |
| s16 | e016 | 2026-07-19T09:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_notice_time, b_notice_access, b_factory_needs, b_notice_rules | team_t1, team_t4 | team_t1, team_t2, team_t3, team_t4 | team_t1, team_t4 | ∅ | e007, e008, e011, e015, e016, h002 | 4 |
| s17 | e017 | 2026-07-21T08:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_count, b_factory_stock, b_factory_cancel, b_factory_open, b_bus_open, b_lunch_open, b_notice_open | team_t1, team_t2, team_t3, team_t4 | ∅ | ∅ | team_t1, team_t2, team_t3, team_t4 | ∅ | 4 |
| s18 | e018 | 2026-07-21T11:20:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_notice_route | ∅ | ∅ | ∅ | ∅ | ∅ | 4 |
| s19 | e019 | 2026-07-24T09:30:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | b_finance_finished, b_lunch_quote, b_finance_tx, b_finance_invoice, b_finance_other, b_finance_open | team_t5 | team_t5 | team_t5 | ∅ | e002, e007, e008, e019, h002 | 0 |
| s20 | e020 | 2026-07-25T18:00:00+08:00 | team_t1, team_t2, team_t3, team_t4, team_t5 | ∅ | ∅ | team_t5 | ∅ | ∅ | e002, e007, e008, e019, h002 | 0 |

### Task transition audit

- `team_t1`: preceding s15; first Ready s16; Ready at s16; leaves at s17.
- `team_t2`: preceding s10; first Ready s11; Ready at s11, s12, s13, s14, s15, s16; leaves at s17.
- `team_t3`: preceding s07; first Ready s08; Ready at s08, s09, s10, s11, s12, s13, s14, s15, s16; leaves at s17.
- `team_t4`: preceding s15; first Ready s16; Ready at s16; leaves at s17.
- `team_t5`: preceding s18; first Ready s19; Ready at s19, s20; leaves at —.
