# Izsoļu monitors

Katru pirmdienu (GitHub Actions) pārbauda:

| Avots | Kas tiek pārbaudīts |
|---|---|
| Possessor — izsoles | https://www.possessor.gov.lv/lv/auctions — katrs jauns izsoles objekts |
| Possessor — jaunumi | https://www.possessor.gov.lv/jaunumi — tikai raksti, kuros minēta izsole / pārdošana / atsavināšana / noma / nekustamais īpašums u.tml. |
| LVĢMC Vides centrs — izsoles | https://videscentrs.lvgmc.lv/lapas/izsoles — nekustamā un kustamā manta, gan pārdošana, gan noma (jauni sludinājumi un dokumenti) |
| LVĢMC Vides centrs — jaunumi | https://videscentrs.lvgmc.lv/jaunumi — tikai ar tiem pašiem atslēgvārdiem |

Ja parādās kas jauns, repozitorijā tiek izveidots **Issue** ar saitēm, un GitHub par to atsūta e-pastu.
Ja kādu lapu neizdodas nolasīt (lapa nepieejama vai mainījusies tās struktūra), Issue tiek izveidots ar brīdinājumu.

- Jau redzētie ieraksti: `state.json` (atjauno automātiski; ja izdzēš kādu avotu no faila, nākamā palaišana to tikai iegaumē bez paziņojuma).
- Atslēgvārdi jaunumiem: `NEWS_KEYWORDS` failā `monitor.py`.
- Palaist ar roku: GitHub → Actions → "Izsoļu monitors" → Run workflow.
- Lokāli: `pip install -r requirements.txt && python monitor.py`
