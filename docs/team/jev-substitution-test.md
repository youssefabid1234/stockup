# Test Jev: "Does this customer accept a replacement?" (Daycem, T3) · Mon. 23/11

To be used in `DECISIONS.md`. Script: [`scripts/jev_substitution_test.py`](../../scripts/jev_substitution_test.py).

**Protocol.** 10 `data/context/clients/` customer records, one yes/no question to Jev per card (10 calls by
no call to the LLM, no writing in the ERP). The correct answer of each sheet was fixed to the hand
**avant** the passage, according to what the form says. Rule: p(yes) ≥ 0,8 → "yes", ≤ 0,2 → "no", otherwise "ask".

- **v1**: Jev receives the line CRM, "What upsets them" and the last notes CRM. General question: "Does he accept
  that he be given another butter when the butter he orders is missing?"
- **v2**: v1 + the paragraph "Who they are". Question: "Does he accept another product instead of butter?
  of AOP laminating butter?"

| Form | Good answer | v1 p(yes) | v1 | v2 p(yes) | v2 |
|---|---|---|---|---|---|
| c0001 Maison Sarrailh | No | 0,04 | OK | 0,04 | OK |
| c0021 Le Pétrin de Colomiers | yes | 0,87 | OK | 0,66 | FAUX (apply) |
| c0097 Au Fournil de Brigitte | No | 0,21 | FAUX (apply) | 0,11 | OK |
| c0102 Au Fournil de Guillaume | ask | 0,92 | FAUX (yes) | 0,82 | FAUX (yes) |
| c0100 Grand Hôtel de Saint-Cyprien | yes | 0,91 | OK | 0,82 | OK |
| c0039 Hôtel Saint-Anh | No | 0,15 | OK | 0,30 | FAUX (apply) |
| c0002 Pâtisserie Lacombe-Viguier | ask | 0,16 | FAUX (no) | 0,19 | FAUX (no) |
| c0012 Pâtisserie Les Carmes | ask | 0,24 | OK | 0,22 | OK |
| c0007 Le Pétrin de Balma | yes | 0,66 | FAUX (apply) | 0,57 | FAUX (apply) |
| c0010 Hôtel Garonne Saint-Pierre | ask | 0,24 | OK | 0,23 | OK |
| **Total** | | | **6/10** | | **5/10** |
| **Average time** (min – max) | | | 150 ms (113 – 227) | | 173 ms (116 – 399) |

**Read.**
- Jev is fast () 150-170 ms and is never mistaken in the dangerous direction on clear refusals (c0001 to 0,04).
- But it is not reliable enough alone: 5 to 6/10, and results that move between the two passages (c0097 corrected,
  c0039 and c0021 gradients). With "Who they are", c0021 and c0102 have the same ** sentence** ("is due to its AOP laminating butter for
  pains au chocolat"); Jev declines c0021 (0,87 → 0,66) but keeps c0102 to "yes" (0,82).
- Thresholds do not separate cases well: "no" goes up to 0,30 and "ask" goes to 0,19-0,24.

**Decision (T3).** Keyword rules first (92 sheets on 104 have a phrase that is quite specific to their preferences:
36 "Refused substitutions", 56 "Accept substitutions"), Jev only when no sentence is found, and client's agreement always requested before
to add a replacement.
