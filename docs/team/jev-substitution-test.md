# Test Jev : « ce client accepte-t-il un remplacement ? » (Daycem, T3) · lun. 23/11

À reprendre dans `DECISIONS.md`. Script : [`scripts/jev_substitution_test.py`](../../scripts/jev_substitution_test.py).

**Protocole.** 10 fiches clients de `data/context/clients/`, une question oui/non à Jev par fiche (10 appels par
passage, aucun appel au LLM, aucune écriture dans l'ERP). La bonne réponse de chaque fiche a été fixée à la main
**avant** le passage, d'après ce que dit la fiche. Règle : p(oui) ≥ 0,8 → « oui », ≤ 0,2 → « non », sinon « demander ».

- **v1** : Jev reçoit la ligne CRM, « Ce qui les agace » et les dernières notes CRM. Question générale : « accepte-t-il
  qu'on lui livre un autre beurre quand le beurre qu'il commande manque ? »
- **v2** : v1 + le paragraphe « Qui ils sont ». Question précise : « accepte-t-il un autre produit à la place du beurre
  de tourage AOP ? »

| Fiche | Bonne réponse | v1 p(oui) | v1 | v2 p(oui) | v2 |
|---|---|---|---|---|---|
| c0001 Maison Sarrailh | non | 0,04 | OK | 0,04 | OK |
| c0021 Le Pétrin de Colomiers | oui | 0,87 | OK | 0,66 | FAUX (demander) |
| c0097 Au Fournil de Brigitte | non | 0,21 | FAUX (demander) | 0,11 | OK |
| c0102 Au Fournil de Guillaume | demander | 0,92 | FAUX (oui) | 0,82 | FAUX (oui) |
| c0100 Grand Hôtel de Saint-Cyprien | oui | 0,91 | OK | 0,82 | OK |
| c0039 Hôtel Saint-Anh | non | 0,15 | OK | 0,30 | FAUX (demander) |
| c0002 Pâtisserie Lacombe-Viguier | demander | 0,16 | FAUX (non) | 0,19 | FAUX (non) |
| c0012 Pâtisserie Les Carmes | demander | 0,24 | OK | 0,22 | OK |
| c0007 Le Pétrin de Balma | oui | 0,66 | FAUX (demander) | 0,57 | FAUX (demander) |
| c0010 Hôtel Garonne Saint-Pierre | demander | 0,24 | OK | 0,23 | OK |
| **Total** | | | **6/10** | | **5/10** |
| **Temps moyen** (min – max) | | | 150 ms (113 – 227) | | 173 ms (116 – 399) |

**Lecture.**
- Jev est rapide (≈ 150-170 ms) et ne se trompe jamais dans le sens dangereux sur les refus clairs (c0001 à 0,04).
- Mais il n'est pas assez fiable seul : 5 à 6/10, et des résultats qui bougent entre les deux passages (c0097 corrigé,
  c0039 et c0021 dégradés). Avec « Qui ils sont », c0021 et c0102 ont la **même phrase** (« tient à son tourage AOP pour
  les chocolatines ») ; Jev baisse c0021 (0,87 → 0,66) mais garde c0102 à « oui » (0,82).
- Les seuils ne séparent pas bien les cas : les « non » vont jusqu'à 0,30 et des « demander » sont à 0,19-0,24.

**Décision (T3).** Règles par mots-clés d'abord (92 fiches sur 104 ont une phrase toute faite dans leurs préférences :
36 « Refuse les substitutions », 56 « Accepte les substitutions »), Jev seulement quand aucune phrase n'est trouvée, et l'accord du client toujours demandé avant
d'ajouter un remplaçant.
