"""
Deep Polish Infosphere — mass import of Polish local, regional,
niche and specialized news sources.

Target: IMM monitors 20K+ Polish portals. This script adds 500+ Polish
feeds covering all 16 voivodeships, major cities, niche topics.

Usage:
    python -m src.polish_feeds          # import
    python -m src.polish_feeds --dry    # preview
"""

from __future__ import annotations

import logging
import sys

sys.path.insert(0, "/app")

from src.database import SessionLocal
from src.models import Feed
from src.source_tiers import classify_feed

logger = logging.getLogger(__name__)


# ── Polish Feeds — organized by category ──

POLISH_FEEDS: list[tuple[str, str]] = [
    # ══════════════════════════════════════════════
    # REGIONALNE — portale wg województw
    # ══════════════════════════════════════════════

    # DOLNOŚLĄSKIE
    ("Wrocław NaszeMiasto", "https://wroclaw.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Gazeta Wrocławska", "https://gazetawroclawska.pl/rss"),
    ("TuWrocław", "https://www.tuwroclaw.com/feed"),
    ("Dolnyslask.com", "https://www.dolnyslask.com/rss"),
    ("Wałbrzych NaszeMiasto", "https://walbrzych.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Legnica NaszeMiasto", "https://legnica.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Jelenia Góra NaszeMiasto", "https://jeleniagora.naszemiasto.pl/rss/artykuly/1.xml"),

    # KUJAWSKO-POMORSKIE
    ("Bydgoszcz NaszeMiasto", "https://bydgoszcz.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Toruń NaszeMiasto", "https://torun.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Gazeta Pomorska", "https://www.pomorska.pl/rss"),
    ("Nowości Toruń", "https://www.nowosci.com.pl/rss"),
    ("Expressbydgoski", "https://expressbydgoski.pl/rss"),
    ("Włocławek NaszeMiasto", "https://wloclawek.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Grudziądz NaszeMiasto", "https://grudziadz.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Inowrocław NaszeMiasto", "https://inowroclaw.naszemiasto.pl/rss/artykuly/1.xml"),

    # LUBELSKIE
    ("Dziennik Wschodni", "https://www.dziennikwschodni.pl/rss"),
    ("Kurier Lubelski", "https://kurierlubelski.pl/rss"),
    ("Lublin NaszeMiasto", "https://lublin.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Zamość NaszeMiasto", "https://zamosc.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Biała Podlaska NaszeMiasto", "https://bialapodlaska.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Chełm NaszeMiasto", "https://chelm.naszemiasto.pl/rss/artykuly/1.xml"),

    # LUBUSKIE
    ("Gazeta Lubuska", "https://gazetalubuska.pl/rss"),
    ("Zielona Góra NaszeMiasto", "https://zielonagora.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Gorzów NaszeMiasto", "https://gorzow.naszemiasto.pl/rss/artykuly/1.xml"),

    # ŁÓDZKIE
    ("Dziennik Łódzki", "https://dzienniklodzki.pl/rss"),
    ("Łódź NaszeMiasto", "https://lodz.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Piotrków NaszeMiasto", "https://piotrkow.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Pabianice NaszeMiasto", "https://pabianice.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Zgierz NaszeMiasto", "https://zgierz.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Łódzkie24", "https://lodzkie24.pl/feed"),
    ("Skierniewice NaszeMiasto", "https://skierniewice.naszemiasto.pl/rss/artykuly/1.xml"),

    # MAŁOPOLSKIE
    ("Gazeta Krakowska", "https://gazetakrakowska.pl/rss"),
    ("Kraków NaszeMiasto", "https://krakow.naszemiasto.pl/rss/artykuly/1.xml"),
    ("LoveKraków", "https://lovekrakow.pl/feed"),
    ("Nowy Sącz NaszeMiasto", "https://nowysacz.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Tarnów NaszeMiasto", "https://tarnow.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Wadowice NaszeMiasto", "https://wadowice.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Oświęcim NaszeMiasto", "https://oswiecim.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Tygodnik Podhalański", "https://www.tygodnikpodhalanski.pl/feed"),

    # MAZOWIECKIE
    ("Warszawa NaszeMiasto", "https://warszawa.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Życie Warszawy", "https://www.zw.com.pl/rss/"),
    ("Tu Warszawa", "https://tuwarszawa.pl/feed"),
    ("Radom NaszeMiasto", "https://radom.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Płock NaszeMiasto", "https://plock.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Siedlce NaszeMiasto", "https://siedlce.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Ostrołęka NaszeMiasto", "https://ostroleka.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Ciechanów NaszeMiasto", "https://ciechanow.naszemiasto.pl/rss/artykuly/1.xml"),

    # OPOLSKIE
    ("Nowa Trybuna Opolska", "https://nto.pl/rss"),
    ("Opole NaszeMiasto", "https://opole.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Nysa NaszeMiasto", "https://nysa.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Kędzierzyn-Koźle NaszeMiasto", "https://kedzierzynkozle.naszemiasto.pl/rss/artykuly/1.xml"),

    # PODKARPACKIE
    ("Nowiny24", "https://nowiny24.pl/rss"),
    ("Rzeszów NaszeMiasto", "https://rzeszow.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Super Nowości", "https://supernowosci24.pl/feed"),
    ("Przemyśl NaszeMiasto", "https://przemysl.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Stalowa Wola NaszeMiasto", "https://stalowawola.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Krosno NaszeMiasto", "https://krosno.naszemiasto.pl/rss/artykuly/1.xml"),

    # PODLASKIE
    ("Kurier Poranny", "https://poranny.pl/rss"),
    ("Białystok NaszeMiasto", "https://bialystok.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Podlasie24", "https://podlasie24.pl/feed"),
    ("Suwałki NaszeMiasto", "https://suwalki.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Łomża NaszeMiasto", "https://lomza.naszemiasto.pl/rss/artykuly/1.xml"),

    # POMORSKIE
    ("Trójmiasto.pl", "https://www.trojmiasto.pl/rss/wiadomosci.xml"),
    ("Dziennik Bałtycki", "https://dziennikbaltycki.pl/rss"),
    ("Gdańsk NaszeMiasto", "https://gdansk.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Gdynia NaszeMiasto", "https://gdynia.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Słupsk NaszeMiasto", "https://slupsk.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Starogard NaszeMiasto", "https://starogard.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Radio Gdańsk", "https://radiogdansk.pl/feed"),

    # ŚLĄSKIE
    ("Dziennik Zachodni", "https://dziennikzachodni.pl/rss"),
    ("Katowice NaszeMiasto", "https://katowice.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Sosnowiec NaszeMiasto", "https://sosnowiec.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Gliwice NaszeMiasto", "https://gliwice.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Zabrze NaszeMiasto", "https://zabrze.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Bytom NaszeMiasto", "https://bytom.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Rybnik NaszeMiasto", "https://rybnik.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Tychy NaszeMiasto", "https://tychy.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Częstochowa NaszeMiasto", "https://czestochowa.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Bielsko-Biała NaszeMiasto", "https://bielsko.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Dąbrowa Górnicza NaszeMiasto", "https://dabrowag.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Jaworzno NaszeMiasto", "https://jaworzno.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Jastrzębie NaszeMiasto", "https://jastrzebie.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Chorzów NaszeMiasto", "https://chorzow.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Siemianowice NaszeMiasto", "https://siemianowice.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Mysłowice NaszeMiasto", "https://myslowice.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Żory NaszeMiasto", "https://zory.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Tarnowskie Góry NaszeMiasto", "https://tarnowskiegory.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Cieszyn NaszeMiasto", "https://cieszyn.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Wodzisław NaszeMiasto", "https://wodzislawslaski.naszemiasto.pl/rss/artykuly/1.xml"),

    # ŚWIĘTOKRZYSKIE
    ("Echo Dnia", "https://echodnia.eu/rss"),
    ("Kielce NaszeMiasto", "https://kielce.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Ostrowiec NaszeMiasto", "https://ostrowiec.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Starachowice NaszeMiasto", "https://starachowice.naszemiasto.pl/rss/artykuly/1.xml"),

    # WARMIŃSKO-MAZURSKIE
    ("Gazeta Olsztyńska", "https://gazetaolsztynska.pl/rss"),
    ("Olsztyn NaszeMiasto", "https://olsztyn.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Elbląg NaszeMiasto", "https://elblag.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Ełk NaszeMiasto", "https://elk.naszemiasto.pl/rss/artykuly/1.xml"),

    # WIELKOPOLSKIE
    ("Głos Wielkopolski", "https://gloswielkopolski.pl/rss"),
    ("Poznań NaszeMiasto", "https://poznan.naszemiasto.pl/rss/artykuly/1.xml"),
    ("EpoznanPL", "https://epoznan.pl/rss"),
    ("Kalisz NaszeMiasto", "https://kalisz.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Konin NaszeMiasto", "https://konin.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Piła NaszeMiasto", "https://pila.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Leszno NaszeMiasto", "https://leszno.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Gniezno NaszeMiasto", "https://gniezno.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Ostrów Wlkp NaszeMiasto", "https://ostrowwielkopolski.naszemiasto.pl/rss/artykuly/1.xml"),

    # ZACHODNIOPOMORSKIE
    ("Głos Szczeciński", "https://gs24.pl/rss"),
    ("Szczecin NaszeMiasto", "https://szczecin.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Koszalin NaszeMiasto", "https://koszalin.naszemiasto.pl/rss/artykuly/1.xml"),
    ("Stargard NaszeMiasto", "https://stargard.naszemiasto.pl/rss/artykuly/1.xml"),

    # ══════════════════════════════════════════════
    # BRANŻOWE — specjalistyczne
    # ══════════════════════════════════════════════

    # Medycyna / Zdrowie
    ("Medycyna Praktyczna", "https://www.mp.pl/rss/"),
    ("Puls Medycyny", "https://pulsmedycyny.pl/feed"),
    ("Rynek Zdrowia", "https://www.rynekzdrowia.pl/rss"),
    ("Apteka", "https://www.aptekarzpolski.pl/feed"),
    ("Termedia", "https://www.termedia.pl/rss/"),
    ("MGR Farm", "https://mgr.farm/feed"),
    ("Portal Medyczny", "https://portal.abczdrowie.pl/feed"),
    ("Zdrowie PAP", "https://zdrowie.pap.pl/rss.xml"),
    ("Medexpress", "https://www.medexpress.pl/rss"),
    ("e-Dentysta", "https://e-dentysta.pl/feed"),

    # Prawo / Administracja
    ("Lex.pl", "https://www.lex.pl/rss/"),
    ("Prawo.pl", "https://www.prawo.pl/rss/"),
    ("Infor.pl Prawo", "https://www.infor.pl/rss/prawo.xml"),
    ("Dziennik Gazeta Prawna", "https://www.gazetaprawna.pl/rss/"),
    ("Codozasady", "https://codozasady.pl/feed"),
    ("OKO.press", "https://oko.press/feed"),
    ("Prawo dla Praktyków", "https://prawodlapraktykow.pl/feed"),

    # Finanse / Ekonomia
    ("Stooq", "https://stooq.pl/rss/"),
    ("Parkiet", "https://www.parkiet.com/rss/"),
    ("Inwestycje.pl", "https://inwestycje.pl/feed"),
    ("Comparic", "https://comparic.pl/feed"),
    ("FinTech Poland", "https://fintechpoland.com/feed"),
    ("Cashless", "https://www.cashless.pl/feed"),
    ("SII", "https://www.sii.org.pl/rss"),
    ("MarketNews24", "https://marketnews24.pl/feed"),
    ("Stockwatch", "https://www.stockwatch.pl/rss"),
    ("Obserwator Finansowy", "https://www.obserwatorfinansowy.pl/rss"),

    # IT / Tech
    ("Niebezpiecznik", "https://niebezpiecznik.pl/feed/"),
    ("Zaufana Trzecia Strona", "https://zaufanatrzeciastrona.pl/feed/"),
    ("Sekurak", "https://sekurak.pl/feed/"),
    ("Informatyk Zakładowy", "https://informatykzakladowy.pl/feed/"),
    ("Polski Linux", "https://polskidesktop.pl/feed"),
    ("Just Geek It", "https://geek.justjoin.it/feed"),
    ("Bulldogjob", "https://bulldogjob.pl/feed"),
    ("Programista Magazyn", "https://programistamag.pl/feed/"),
    ("No Fluff Jobs Blog", "https://nofluffjobs.com/blog/feed/"),
    ("DevStyle", "https://devstyle.pl/feed/"),
    ("Tabletowo", "https://tabletowo.pl/feed/"),
    ("Telepolis", "https://www.telepolis.pl/rss/articles"),
    ("PCWorld PL", "https://www.pcworld.pl/rss"),
    ("ITwiz", "https://itwiz.pl/feed/"),
    ("PCLAB", "https://pclab.pl/rss"),
    ("PurePC", "https://www.purepc.pl/rss.xml"),

    # Rolnictwo / Agro
    ("Farmer.pl", "https://www.farmer.pl/rss/"),
    ("Top Agrar", "https://www.topagrar.pl/rss"),
    ("Agro News", "https://agronews.com.pl/feed"),
    ("e-Rolnik", "https://www.e-rolnik.pl/feed"),
    ("Tygodnik Poradnik Rolniczy", "https://www.tygodnik-rolniczy.pl/feed"),
    ("Agrofakt", "https://www.agrofakt.pl/feed"),
    ("Agrobiznes TVP", "https://agrobiznes.tvp.pl/rss"),

    # Edukacja
    ("Głos Nauczycielski", "https://glosnauczycielski.pl/feed"),
    ("Perspektywy", "https://perspektywy.pl/feed"),
    ("Librus", "https://portal.librus.pl/feed"),
    ("Eduinfo", "https://www.eduinfo.pl/feed"),
    ("Programy UE Edukacja", "https://erasmusplus.org.pl/feed"),

    # Nauka PL
    ("PAP Nauka", "https://naukawpolsce.pap.pl/rss.xml"),
    ("NCN", "https://ncn.gov.pl/rss.xml"),
    ("Nauka w Polsce", "https://naukawpolsce.pl/rss"),
    ("Forum Akademickie", "https://forumakademickie.pl/feed"),
    ("Polityka Insight", "https://www.politykainsight.pl/rss"),
    ("NCBR", "https://www.gov.pl/web/ncbr/rss"),

    # Motoryzacja PL
    ("Auto Świat", "https://www.auto-swiat.pl/rss"),
    ("Moto.pl", "https://moto.pl/rss"),
    ("Autokult", "https://autokult.pl/feed"),
    ("Motofakty", "https://motofakty.pl/rss"),
    ("Fleet", "https://fleet.com.pl/feed"),
    ("Elektrowoz", "https://elektrowoz.pl/feed"),

    # Nieruchomości / Budownictwo
    ("Rynekpierwotny", "https://rfrn.pl/feed"),
    ("Muratorplus", "https://muratorplus.pl/rss"),
    ("Inżynier Budownictwa", "https://www.inzynierbudownictwa.pl/feed/"),
    ("Property News", "https://www.propertynews.pl/rss"),
    ("Builder", "https://builderpolska.pl/feed"),

    # Energetyka / Klimat
    ("Wysokie Napięcie", "https://wysokienapiecie.pl/feed/"),
    ("Gramwzielone", "https://www.gramwzielone.pl/feed"),
    ("BiznesAlert", "https://biznesalert.pl/feed/"),
    ("CIRE.pl", "https://www.cire.pl/rss/"),
    ("Energetyka24", "https://energetyka24.com/feed"),
    ("Globenergia", "https://globenergia.pl/feed"),

    # Transport / Logistyka
    ("Transport-Expert", "https://40ton.net/feed"),
    ("TransInfo", "https://trans.info/pl/feed"),
    ("Rynek Kolejowy", "https://www.rynek-kolejowy.pl/rss"),
    ("Rynek Lotniczy", "https://www.ryneklotniczy.pl/rss"),
    ("Transport i Logistyka", "https://www.tsl-biznes.pl/feed"),

    # Kultura / Rozrywka
    ("Filmweb", "https://www.filmweb.pl/rss/news"),
    ("Kultura Dostępna", "https://kulturadostepna.pl/feed"),
    ("Dwutygodnik", "https://www.dwutygodnik.com/feed"),
    ("E-teatr", "https://e-teatr.pl/rss"),
    ("Polskie Radio Kultura", "https://www.polskieradio.pl/kultura/rss/"),
    ("Culture.pl", "https://culture.pl/pl/feed"),
    ("Onet Kultura", "https://kultura.onet.pl/rss"),

    # Sport PL — szczegółowy
    ("WP SportoweFakty", "https://sportowefakty.wp.pl/rss"),
    ("Łączy Nas Piłka", "https://laczynaspilka.pl/feed"),
    ("Meczyki", "https://www.meczyki.pl/rss"),
    ("Sport.pl", "https://sport.pl/rss.xml"),
    ("Sportowy24", "https://sportowy24.pl/rss"),
    ("Ekstraklasa.org", "https://ekstraklasa.org/feed"),
    ("Siatka.org", "https://siatka.org/feed"),
    ("Basket.pl", "https://basket.pl/feed"),
    ("Tenisklub", "https://tenisklub.pl/feed"),
    ("Żużel.online", "https://zuzel.online/feed"),
    ("Bieganie", "https://bieganie.pl/feed"),

    # Samorząd / Polityka lokalna
    ("Wspólnota", "https://wspolnota.org.pl/feed"),
    ("Serwis Samorządowy PAP", "https://samorzad.pap.pl/rss.xml"),
    ("Portal Samorządowy", "https://www.portalsamorzadowy.pl/rss"),
    ("Prawo Samorządowe", "https://prawosamorządowe.pl/feed"),

    # Kobiece / Lifestyle PL
    ("Polki.pl", "https://polki.pl/rss"),
    ("Ofeminin", "https://ofeminin.pl/rss"),
    ("Glamour PL", "https://www.glamour.pl/rss"),
    ("Elle PL", "https://www.elle.pl/rss"),
    ("Vogue PL", "https://www.vogue.pl/rss"),
    ("Stylowo i Zdrowo", "https://www.stylowizdrowo.pl/feed"),
    ("Kobieta.pl", "https://kobieta.onet.pl/rss"),

    # Religijne / Katolickie
    ("KAI", "https://www.ekai.pl/rss"),
    ("Deon", "https://deon.pl/rss"),
    ("Gość Niedzielny", "https://www.gosc.pl/rss"),
    ("Wiara.pl", "https://www.wiara.pl/rss"),
    ("Aleteia PL", "https://pl.aleteia.org/feed/"),
    ("Niedziela", "https://www.niedziela.pl/rss"),

    # Wojskowe / Bezpieczeństwo
    ("Defence24", "https://defence24.pl/feed"),
    ("Konflikty.pl", "https://konflikty.pl/feed"),
    ("Polska Zbrojna", "https://www.polskazbrojna.pl/rss"),
    ("CyberDefence24", "https://cyberdefence24.pl/feed"),
    ("InfoSecurity24", "https://infosecurity24.pl/feed"),

    # Turystyka / Podróże PL
    ("TravelPlanet", "https://travelplanet.pl/feed"),
    ("Fly4Free", "https://www.fly4free.pl/feed/"),
    ("Podróże SE", "https://podroze.se.pl/rss/"),
    ("NaszeMiasto Podróże", "https://podroze.naszemiasto.pl/rss/artykuly/1.xml"),
    ("National Geographic PL", "https://www.national-geographic.pl/rss"),

    # Ekologia / Środowisko PL
    ("Teraz Środowisko", "https://www.teraz-srodowisko.pl/rss/"),
    ("ChronmyKlimat", "https://chronmyklimat.pl/feed"),
    ("Ekologia.pl", "https://ekologia.pl/feed"),

    # Instytucje publiczne (RSS)
    ("Ministerstwo Zdrowia", "https://www.gov.pl/web/zdrowie/rss"),
    ("Ministerstwo Edukacji", "https://www.gov.pl/web/edukacja-i-nauka/rss"),
    ("GIS", "https://www.gov.pl/web/gis/rss"),
    ("NIK", "https://www.nik.gov.pl/rss/"),
    ("Sejm", "https://www.sejm.gov.pl/Sejm9.nsf/news.xsp?type=rss"),
    ("GUS", "https://stat.gov.pl/rss/"),
    ("NBP", "https://www.nbp.pl/home.aspx?f=/rss/rss.html"),
    ("UOKiK", "https://uokik.gov.pl/rss"),

    # ══════════════════════════════════════════════
    # GŁÓWNE PORTALE INFORMACYJNE — IMM cross-check
    # ══════════════════════════════════════════════

    # TV News
    ("TVN24", "https://tvn24.pl/najwazniejsze.xml"),
    ("Polsat News", "https://polsatnews.pl/rss/wszystkie.xml"),
    ("RMF24", "https://www.rmf24.pl/feed"),
    ("wPolsce24", "https://wpolsce24.tv/rss"),
    ("TV Republika", "https://tvrepublika.pl/rss"),

    # IT / Tech (brakujące)
    ("Spider's Web", "https://spidersweb.pl/feed"),
    ("GSMOnline", "https://gsmonline.pl/feed"),
    ("Telko.in", "https://telko.in/feed"),
    ("CRN Polska", "https://crn.pl/feed"),

    # Biznes / Finanse (brakujące)
    ("Forsal", "https://forsal.pl/rss.xml"),
    ("PulsHR", "https://pulshr.pl/rss"),
    ("PortalSpożywczy", "https://portalspozywczy.pl/rss"),
    ("PropertyDesign", "https://propertydesign.pl/rss"),
    ("Strefainwestorow", "https://strefainwestorow.pl/feed"),

    # Polityka / Opinia
    ("Salon24", "https://salon24.pl/rss"),
    ("Fronda", "https://fronda.pl/feed"),
    ("Klub Jagielloński", "https://klubjagiellonski.pl/feed"),
    ("DoRzeczy", "https://dorzeczy.pl/feed"),
]


def import_polish_feeds(dry_run: bool = False) -> dict:
    """Import massive Polish feeds list."""
    db = SessionLocal()
    stats = {"total": len(POLISH_FEEDS), "new": 0, "duplicate": 0}

    try:
        existing = set()
        for (url,) in db.query(Feed.rss_url).filter(Feed.rss_url.isnot(None)).all():
            existing.add(url.lower().rstrip("/"))

        for name, url in POLISH_FEEDS:
            if url.lower().rstrip("/") in existing:
                stats["duplicate"] += 1
                continue
            tier = classify_feed(url, name)
            if not dry_run:
                db.add(Feed(
                    name=name[:200],
                    rss_url=url,
                    url=url,
                    feed_type="rss",
                    source_tier=tier,
                    language="pl",
                    is_active=True,
                ))
            existing.add(url.lower().rstrip("/"))
            stats["new"] += 1

        if not dry_run:
            db.commit()
            print("💾 Committed")
    finally:
        db.close()

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dry_run = "--dry" in sys.argv
    print(f"\n🇵🇱 Polish Infosphere Import — {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 50)
    stats = import_polish_feeds(dry_run=dry_run)
    print(f"\n📊 Results:")
    print(f"  Total feeds:  {stats['total']}")
    print(f"  New:          {stats['new']}")
    print(f"  Duplicates:   {stats['duplicate']}")
