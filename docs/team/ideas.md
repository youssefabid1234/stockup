# Ideas File (in order of priority)

> You can only touch ** after the ** essential (quite and fast control). You take the ** ideas from the top**.
> add one (who proposed it and why); reorder the sync. The CTO allows to change everything: ERP,
> tables, data, features, "as long as it gives something nice".

| # | Idea | Why (criterion / source) | Who could wear it | Size |
|---|---|---|---|---|
| 0 | **The agent speaks first and greets the caller by his name** ("Hello Nadine, Le Fournil Occitan, what can I do for you?") from "Start the call", thanks to the file already loaded. Fixed phrase without a call to the model (≈ 0 s waiting). A 1re version exists (PR #14: "Hello Madam/Monsieur" prepared during the loading of the plug); remains to say the **nom** and to speak **avant** that the customer speaks | Natural + Fast — requested by Youssef (24/11) | Mohamed Amine | S |
| 1 | **Change voice**: the current voice speaks a bad French and does not sound natural (choose a French voice ElevenLabs, more expressive model, or another supplier; listen and compare) | Natural — remark by Youssef (CTO also sensitive to natural) | Mohamed Amine (voice) | S |
| 2 | **Jev for quick decisions**: classify the customer's sentence (simple / need of ERP), agreement or refusal of a substitute | Fast — advised by the CTO ("can be very useful for voice"), provided in T4 of Youssef | Youssef (T4) | M |
| 3 | **Correct conflicting data** (notes "Closed Wednesday" of 9 customers while ERP and history deliver them on Wednesday) in the ERP itself | Intelligent — decision Youssef: ERP + historical are authentic; the CTO allows to modify the data. Today processed by the rules (A1, Amine K.) and the preloaded sheet (A2, Youssef) | Amine K. or Youssef | S |
| 4 | **A parallel outbound call campaign to sell stock**: the agent calls bakeries who buy laminating butter to place the laminating butter 82 % on a promo (or a product close to the deadline) | Impressive — example of CTO ("agents calling 100 conservators in parallel") ; prolongs the demo promo of Daycem and the parallelism of Youssef | Youssef + Daycem | L |
| 5 | **SAV with stock context**: claim (incomplete delivery, damaged product) + immediate solution depending on stock (delivery, have) | Planned case 2 (S08); example of CTO | Amine K. | M |
| 6 | **Negotiation parallel suppliers**: Call butter suppliers during breakup AOP to compare prices | Example of CTO; actual data (rupture, 218 negotiations, purchase order draft) | to be seen | L |
