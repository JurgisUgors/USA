# Izsoļu monitors

Katru pirmdienu (GitHub Actions) pārbauda:
- https://www.possessor.gov.lv/lv/auctions
- https://videscentrs.lvgmc.lv/

un meklē jaunus sludinājumus par izsolēm vai pārdošanu (nekustamie īpašumi, kustamā manta, kapitāldaļas, uzņēmumi u.c.).
Ja parādās kas jauns, repozitorijā tiek izveidots **Issue**, un GitHub par to atsūta e-pastu.

- Lapas un atslēgvārdi: `sites.json` (var pievienot vēl lapas).
- Jau redzētie sludinājumi: `state.json` (tiek atjaunots automātiski).
- Palaist ar roku: GitHub → Actions → "Izsoļu monitors" → Run workflow.
- Pirmā palaišana tikai saglabā esošo stāvokli un neko nesūta.
