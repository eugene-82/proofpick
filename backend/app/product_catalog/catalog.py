"""Validated Phase 1 catalog used for exact demo input canonicalization."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .models import CatalogCategory, DemoProduct, ProductLifecycle
from .normalize import normalize_catalog_alias


class CatalogValidationError(ValueError):
    """Raised when catalog identities or safe aliases are not deterministic."""


_KOREAN_BRANDS = {
    "Apple": "애플", "Samsung": "삼성", "Sony": "소니", "Bose": "보스",
    "JBL": "제이비엘", "Sennheiser": "젠하이저", "Beats": "비츠",
    "Audio-Technica": "오디오테크니카", "Google": "구글",
    "Logitech": "로지텍", "ASUS": "에이수스", "LG": "엘지", "Dell": "델",
    "Razer": "레이저", "BenQ": "벤큐", "Roborock": "로보락",
    "Dreame": "드리미", "Dyson": "다이슨", "ECOVACS": "에코백스",
    "Narwal": "나르왈", "Nintendo": "닌텐도", "Valve": "밸브",
    "Microsoft": "마이크로소프트", "Lenovo": "레노버", "MSI": "엠에스아이",
    "Meta": "메타",
}


def _product(canonical_id: str, canonical_name: str, brand: str, category: CatalogCategory,
             subcategory: str, family: str, generation: str | None,
             lifecycle: ProductLifecycle, korean_alias: str,
             demo_rank: int | None = None) -> DemoProduct:
    product_name = canonical_name.removeprefix(f"{brand} ")
    return DemoProduct(
        canonical_id=canonical_id, canonical_name=canonical_name, brand=brand,
        category=category, subcategory=subcategory, family=family,
        generation=generation, lifecycle=lifecycle,
        aliases=(product_name, f"{_KOREAN_BRANDS[brand]} {product_name}", korean_alias),
        demo_rank=demo_rank,
    )


C = CatalogCategory
L = ProductLifecycle


PRODUCTS: tuple[DemoProduct, ...] = (
    # Audio (15)
    _product("apple.airpods-pro.3", "Apple AirPods Pro 3", "Apple", C.AUDIO, "wireless_earbuds", "AirPods Pro", "3", L.CURRENT, "에어팟프로3", 1),
    _product("samsung.galaxy-buds4-pro", "Samsung Galaxy Buds4 Pro", "Samsung", C.AUDIO, "wireless_earbuds", "Galaxy Buds Pro", "4", L.CURRENT, "갤럭시버즈4프로", 2),
    _product("sony.wh-1000xm6", "Sony WH-1000XM6", "Sony", C.AUDIO, "headphones", "WH-1000XM", "6", L.CURRENT, "소니 WH1000XM6", 3),
    _product("bose.quietcomfort-ultra-headphones.2", "Bose QuietComfort Ultra Headphones 2nd Gen", "Bose", C.AUDIO, "headphones", "QuietComfort Ultra Headphones", "2", L.CURRENT, "보스 QC 울트라 헤드폰 2세대", 4),
    _product("jbl.charge.6", "JBL Charge 6", "JBL", C.AUDIO, "portable_speaker", "Charge", "6", L.CURRENT, "JBL 차지6", 5),
    _product("apple.airpods.4", "Apple AirPods 4", "Apple", C.AUDIO, "wireless_earbuds", "AirPods", "4", L.CURRENT, "에어팟4"),
    _product("apple.airpods-max.2", "Apple AirPods Max 2", "Apple", C.AUDIO, "headphones", "AirPods Max", "2", L.CURRENT, "에어팟맥스2"),
    _product("samsung.galaxy-buds3-pro", "Samsung Galaxy Buds3 Pro", "Samsung", C.AUDIO, "wireless_earbuds", "Galaxy Buds Pro", "3", L.RECENT, "갤럭시버즈3프로"),
    _product("sony.wf-1000xm5", "Sony WF-1000XM5", "Sony", C.AUDIO, "wireless_earbuds", "WF-1000XM", "5", L.RECENT, "소니 WF1000XM5"),
    _product("bose.quietcomfort-ultra-earbuds.2", "Bose QuietComfort Ultra Earbuds 2nd Gen", "Bose", C.AUDIO, "wireless_earbuds", "QuietComfort Ultra Earbuds", "2", L.CURRENT, "보스 QC 울트라 이어버드 2세대"),
    _product("sennheiser.momentum.4", "Sennheiser Momentum 4 Wireless", "Sennheiser", C.AUDIO, "headphones", "Momentum Wireless", "4", L.STEADY, "젠하이저 모멘텀4"),
    _product("sennheiser.momentum-true-wireless.4", "Sennheiser Momentum True Wireless 4", "Sennheiser", C.AUDIO, "wireless_earbuds", "Momentum True Wireless", "4", L.RECENT, "젠하이저 MTW4"),
    _product("beats.powerbeats-pro.2", "Beats Powerbeats Pro 2", "Beats", C.AUDIO, "wireless_earbuds", "Powerbeats Pro", "2", L.CURRENT, "파워비츠프로2"),
    _product("jbl.flip.7", "JBL Flip 7", "JBL", C.AUDIO, "portable_speaker", "Flip", "7", L.CURRENT, "JBL 플립7"),
    _product("audio-technica.ath-m50xbt2", "Audio-Technica ATH-M50xBT2", "Audio-Technica", C.AUDIO, "headphones", "ATH-M50xBT", "2", L.STEADY, "오디오테크니카 M50xBT2"),
    # Smartphones / tablets / wearables (15)
    _product("apple.iphone.17-pro", "Apple iPhone 17 Pro", "Apple", C.SMART, "smartphone", "iPhone Pro", "17", L.CURRENT, "아이폰17프로", 1),
    _product("samsung.galaxy-s26-ultra", "Samsung Galaxy S26 Ultra", "Samsung", C.SMART, "smartphone", "Galaxy S Ultra", "26", L.CURRENT, "갤럭시S26울트라", 2),
    _product("google.pixel.10-pro", "Google Pixel 10 Pro", "Google", C.SMART, "smartphone", "Pixel Pro", "10", L.CURRENT, "픽셀10프로", 3),
    _product("samsung.galaxy-z-fold7", "Samsung Galaxy Z Fold7", "Samsung", C.SMART, "foldable_phone", "Galaxy Z Fold", "7", L.CURRENT, "갤럭시Z폴드7", 4),
    _product("apple.ipad-pro-11.m5", "Apple iPad Pro 11-inch M5", "Apple", C.SMART, "tablet", "iPad Pro 11-inch", "M5", L.CURRENT, "아이패드프로11 M5", 5),
    _product("apple.iphone.17", "Apple iPhone 17", "Apple", C.SMART, "smartphone", "iPhone", "17", L.CURRENT, "아이폰17"),
    _product("apple.iphone.17-pro-max", "Apple iPhone 17 Pro Max", "Apple", C.SMART, "smartphone", "iPhone Pro Max", "17", L.CURRENT, "아이폰17프로맥스"),
    _product("samsung.galaxy-s26", "Samsung Galaxy S26", "Samsung", C.SMART, "smartphone", "Galaxy S", "26", L.CURRENT, "갤럭시S26"),
    _product("google.pixel.10", "Google Pixel 10", "Google", C.SMART, "smartphone", "Pixel", "10", L.CURRENT, "픽셀10"),
    _product("samsung.galaxy-z-flip7", "Samsung Galaxy Z Flip7", "Samsung", C.SMART, "foldable_phone", "Galaxy Z Flip", "7", L.CURRENT, "갤럭시Z플립7"),
    _product("apple.ipad-air-11.m3", "Apple iPad Air 11-inch M3", "Apple", C.SMART, "tablet", "iPad Air 11-inch", "M3", L.RECENT, "아이패드에어11 M3"),
    _product("samsung.galaxy-tab-s11-ultra", "Samsung Galaxy Tab S11 Ultra", "Samsung", C.SMART, "tablet", "Galaxy Tab S Ultra", "11", L.CURRENT, "갤럭시탭S11울트라"),
    _product("apple.watch-series.11", "Apple Watch Series 11", "Apple", C.SMART, "smartwatch", "Apple Watch Series", "11", L.CURRENT, "애플워치11"),
    _product("samsung.galaxy-watch8", "Samsung Galaxy Watch8", "Samsung", C.SMART, "smartwatch", "Galaxy Watch", "8", L.CURRENT, "갤럭시워치8"),
    _product("google.pixel-watch.4", "Google Pixel Watch 4", "Google", C.SMART, "smartwatch", "Pixel Watch", "4", L.CURRENT, "픽셀워치4"),
    # PC peripherals / displays (15)
    _product("logitech.mx-master.4", "Logitech MX Master 4", "Logitech", C.PC, "mouse", "MX Master", "4", L.CURRENT, "MX 마스터 4", 1),
    _product("logitech.mx-master.3s", "Logitech MX Master 3S", "Logitech", C.PC, "mouse", "MX Master", "3S", L.STEADY, "MX 마스터 3S", 2),
    _product("asus.rog-swift-oled.pg27ucdm", "ASUS ROG Swift OLED PG27UCDM", "ASUS", C.PC, "monitor", "ROG Swift OLED", "PG27UCDM", L.CURRENT, "에이수스 PG27UCDM", 3),
    _product("lg.ultragear.32gs95ue-b", "LG UltraGear 32GS95UE-B", "LG", C.PC, "monitor", "UltraGear", "32GS95UE-B", L.RECENT, "울트라기어 32GS95UEB", 4),
    _product("dell.alienware.aw3225qf", "Dell Alienware AW3225QF", "Dell", C.PC, "monitor", "Alienware", "AW3225QF", L.RECENT, "에일리언웨어 AW3225QF", 5),
    _product("logitech.g-pro-x-superlight.2", "Logitech G Pro X Superlight 2", "Logitech", C.PC, "mouse", "G Pro X Superlight", "2", L.RECENT, "지프로 슈퍼라이트2"),
    _product("logitech.mx-keys-s", "Logitech MX Keys S", "Logitech", C.PC, "keyboard", "MX Keys", "S", L.STEADY, "로지텍 MX 키즈 S"),
    _product("razer.deathadder-v4-pro", "Razer DeathAdder V4 Pro", "Razer", C.PC, "mouse", "DeathAdder Pro", "V4", L.CURRENT, "데스에더 V4 프로"),
    _product("razer.blackwidow-v4-pro", "Razer BlackWidow V4 Pro", "Razer", C.PC, "keyboard", "BlackWidow Pro", "V4", L.RECENT, "블랙위도우 V4 프로"),
    _product("asus.rog-swift-oled.pg32ucdm", "ASUS ROG Swift OLED PG32UCDM", "ASUS", C.PC, "monitor", "ROG Swift OLED", "PG32UCDM", L.RECENT, "에이수스 PG32UCDM"),
    _product("lg.ultragear.27gx790a-b", "LG UltraGear 27GX790A-B", "LG", C.PC, "monitor", "UltraGear", "27GX790A-B", L.CURRENT, "울트라기어 27GX790AB"),
    _product("dell.ultrasharp.u3225qe", "Dell UltraSharp U3225QE", "Dell", C.PC, "monitor", "UltraSharp", "U3225QE", L.CURRENT, "울트라샤프 U3225QE"),
    _product("samsung.odyssey-oled-g8.g80sd", "Samsung Odyssey OLED G8 G80SD", "Samsung", C.PC, "monitor", "Odyssey OLED G8", "G80SD", L.RECENT, "오디세이 G80SD"),
    _product("benq.zowie.xl2586x-plus", "BenQ ZOWIE XL2586X Plus", "BenQ", C.PC, "monitor", "ZOWIE XL", "XL2586X Plus", L.CURRENT, "조위 XL2586X 플러스"),
    _product("logitech.g915-x-lightspeed", "Logitech G915 X Lightspeed", "Logitech", C.PC, "keyboard", "G915 X", "Lightspeed", L.CURRENT, "로지텍 G915 X"),
    # Home cleaning / personal appliances (15)
    _product("roborock.saros.10r", "Roborock Saros 10R", "Roborock", C.HOME, "robot_vacuum", "Saros", "10R", L.CURRENT, "사로스10R", 1),
    _product("roborock.qrevo-curv", "Roborock Qrevo Curv", "Roborock", C.HOME, "robot_vacuum", "Qrevo", "Curv", L.CURRENT, "큐레보 커브", 2),
    _product("dreame.x50-ultra", "Dreame X50 Ultra", "Dreame", C.HOME, "robot_vacuum", "X Ultra", "50", L.CURRENT, "드리미X50울트라", 3),
    _product("dyson.gen5detect", "Dyson Gen5detect", "Dyson", C.HOME, "cordless_vacuum", "Gen Detect", "5", L.RECENT, "다이슨 젠5 디텍트", 4),
    _product("dyson.airwrap-id", "Dyson Airwrap i.d.", "Dyson", C.HOME, "hair_styler", "Airwrap", "i.d.", L.CURRENT, "다이슨 에어랩 아이디", 5),
    _product("roborock.saros-z70", "Roborock Saros Z70", "Roborock", C.HOME, "robot_vacuum", "Saros", "Z70", L.CURRENT, "사로스Z70"),
    _product("roborock.qrevo-master", "Roborock Qrevo Master", "Roborock", C.HOME, "robot_vacuum", "Qrevo", "Master", L.RECENT, "큐레보 마스터"),
    _product("roborock.q-revo", "Roborock Q Revo", "Roborock", C.HOME, "robot_vacuum", "Q Revo", None, L.STEADY, "로보락 큐레보"),
    _product("dreame.l40-ultra", "Dreame L40 Ultra", "Dreame", C.HOME, "robot_vacuum", "L Ultra", "40", L.RECENT, "드리미L40울트라"),
    _product("dreame.x40-ultra", "Dreame X40 Ultra", "Dreame", C.HOME, "robot_vacuum", "X Ultra", "40", L.RECENT, "드리미X40울트라"),
    _product("dyson.v15-detect", "Dyson V15 Detect", "Dyson", C.HOME, "cordless_vacuum", "V Detect", "15", L.STEADY, "다이슨V15"),
    _product("dyson.washg1", "Dyson WashG1", "Dyson", C.HOME, "wet_floor_cleaner", "WashG", "1", L.RECENT, "다이슨 워시G1"),
    _product("dyson.supersonic-nural", "Dyson Supersonic Nural", "Dyson", C.HOME, "hair_dryer", "Supersonic", "Nural", L.RECENT, "슈퍼소닉 뉴럴"),
    _product("ecovacs.deebot-x8-pro-omni", "ECOVACS DEEBOT X8 PRO OMNI", "ECOVACS", C.HOME, "robot_vacuum", "DEEBOT X PRO OMNI", "8", L.CURRENT, "디봇 X8 프로 옴니"),
    _product("narwal.freo-z-ultra", "Narwal Freo Z Ultra", "Narwal", C.HOME, "robot_vacuum", "Freo", "Z Ultra", L.RECENT, "프레오 Z 울트라"),
    # Gaming hardware (15)
    _product("nintendo.switch.2", "Nintendo Switch 2", "Nintendo", C.GAMING, "handheld_console", "Switch", "2", L.CURRENT, "닌텐도스위치2", 1),
    _product("sony.playstation.5-pro", "Sony PlayStation 5 Pro", "Sony", C.GAMING, "console", "PlayStation Pro", "5", L.CURRENT, "PS5 Pro", 2),
    _product("valve.steam-deck-oled", "Valve Steam Deck OLED", "Valve", C.GAMING, "handheld_console", "Steam Deck", "OLED", L.RECENT, "스팀덱 OLED", 3),
    _product("asus.rog-xbox-ally-x", "ASUS ROG Xbox Ally X", "ASUS", C.GAMING, "handheld_console", "ROG Xbox Ally", "X", L.CURRENT, "엑스박스 앨라이 X", 4),
    _product("sony.playstation-portal", "Sony PlayStation Portal", "Sony", C.GAMING, "remote_player", "PlayStation Portal", None, L.RECENT, "플레이스테이션 포털", 5),
    _product("nintendo.switch-oled", "Nintendo Switch OLED Model", "Nintendo", C.GAMING, "handheld_console", "Switch", "OLED", L.STEADY, "닌텐도스위치올레드"),
    _product("microsoft.xbox-series-x", "Microsoft Xbox Series X", "Microsoft", C.GAMING, "console", "Xbox Series", "X", L.STEADY, "엑스박스 시리즈 X"),
    _product("microsoft.xbox-series-s", "Microsoft Xbox Series S", "Microsoft", C.GAMING, "console", "Xbox Series", "S", L.STEADY, "엑스박스 시리즈 S"),
    _product("sony.playstation.5", "Sony PlayStation 5", "Sony", C.GAMING, "console", "PlayStation", "5", L.STEADY, "플스5"),
    _product("asus.rog-ally-x", "ASUS ROG Ally X", "ASUS", C.GAMING, "handheld_console", "ROG Ally", "X", L.RECENT, "로그 앨라이 X"),
    _product("lenovo.legion-go-s", "Lenovo Legion Go S", "Lenovo", C.GAMING, "handheld_console", "Legion Go", "S", L.CURRENT, "리전고 S"),
    _product("msi.claw-8-ai-plus", "MSI Claw 8 AI Plus", "MSI", C.GAMING, "handheld_console", "Claw AI Plus", "8", L.RECENT, "MSI 클로8"),
    _product("razer.wolverine-v3-pro", "Razer Wolverine V3 Pro", "Razer", C.GAMING, "controller", "Wolverine Pro", "V3", L.RECENT, "울버린 V3 프로"),
    _product("logitech.g-cloud", "Logitech G Cloud", "Logitech", C.GAMING, "handheld_console", "G Cloud", None, L.STEADY, "로지텍 지클라우드"),
    _product("meta.quest.3", "Meta Quest 3", "Meta", C.GAMING, "vr_headset", "Quest", "3", L.RECENT, "메타퀘스트3"),
)


AMBIGUOUS_ALIASES = frozenset({
    "AirPods Pro", "에어팟 프로", "Galaxy Buds Pro", "갤럭시 버즈 프로",
    "MX Master", "MX 마스터", "Qrevo", "큐레보", "Nintendo Switch",
    "닌텐도 스위치", "PlayStation", "플레이스테이션",
})


class DemoProductCatalog:
    """Exact O(1) lookup index with fail-fast collision validation."""

    def __init__(self, products: Iterable[DemoProduct], *, ambiguous_aliases: Iterable[str] = ()) -> None:
        self.products = tuple(products)
        self.ambiguous_aliases = frozenset(normalize_catalog_alias(alias) for alias in ambiguous_aliases)
        if "" in self.ambiguous_aliases:
            raise CatalogValidationError("ambiguous aliases must not be empty")
        ids = [product.canonical_id for product in self.products]
        if len(ids) != len(set(ids)):
            raise CatalogValidationError("canonical product IDs must be unique")
        index: dict[str, DemoProduct] = {}
        for product in self.products:
            for alias in (product.canonical_name, *product.aliases):
                normalized = normalize_catalog_alias(alias)
                if not normalized:
                    raise CatalogValidationError(f"empty safe alias for {product.canonical_id}")
                existing = index.get(normalized)
                if existing and existing.canonical_id != product.canonical_id:
                    raise CatalogValidationError(
                        f"duplicate normalized SAFE alias {alias!r}: {existing.canonical_id} vs {product.canonical_id}"
                    )
                index[normalized] = product
        overlap = self.ambiguous_aliases.intersection(index)
        if overlap:
            raise CatalogValidationError(f"aliases cannot be SAFE and AMBIGUOUS: {sorted(overlap)!r}")
        self._safe_alias_index = index

    @property
    def safe_alias_count(self) -> int:
        return len(self._safe_alias_index)

    @property
    def category_counts(self) -> dict[CatalogCategory, int]:
        return dict(Counter(product.category for product in self.products))

    def find(self, value: str) -> DemoProduct | None:
        normalized = normalize_catalog_alias(value)
        if not normalized or normalized in self.ambiguous_aliases:
            return None
        return self._safe_alias_index.get(normalized)

    def canonicalize(self, value: str) -> str:
        product = self.find(value)
        return product.canonical_name if product else value


DEMO_PRODUCT_CATALOG = DemoProductCatalog(PRODUCTS, ambiguous_aliases=AMBIGUOUS_ALIASES)

