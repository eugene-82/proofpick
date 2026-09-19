export interface RecommendedProduct {
  displayName: string;
  canonicalName: string;
}

export interface RecommendedProductGroup {
  category: string;
  products: readonly RecommendedProduct[];
}

export const recommendedProductGroups: readonly RecommendedProductGroup[] = [
  { category: "오디오", products: [
    { displayName: "에어팟 프로 3", canonicalName: "Apple AirPods Pro 3" },
    { displayName: "갤럭시 버즈4 프로", canonicalName: "Samsung Galaxy Buds4 Pro" },
    { displayName: "소니 WH-1000XM6", canonicalName: "Sony WH-1000XM6" },
    { displayName: "보스 QC 울트라 2세대", canonicalName: "Bose QuietComfort Ultra Headphones 2nd Gen" },
    { displayName: "JBL 차지 6", canonicalName: "JBL Charge 6" },
  ] },
  { category: "스마트 기기", products: [
    { displayName: "아이폰 17 프로", canonicalName: "Apple iPhone 17 Pro" },
    { displayName: "갤럭시 S26 울트라", canonicalName: "Samsung Galaxy S26 Ultra" },
    { displayName: "픽셀 10 프로", canonicalName: "Google Pixel 10 Pro" },
    { displayName: "갤럭시 Z 폴드7", canonicalName: "Samsung Galaxy Z Fold7" },
    { displayName: "아이패드 프로 11 M5", canonicalName: "Apple iPad Pro 11-inch M5" },
  ] },
  { category: "PC · 디스플레이", products: [
    { displayName: "MX 마스터 4", canonicalName: "Logitech MX Master 4" },
    { displayName: "MX 마스터 3S", canonicalName: "Logitech MX Master 3S" },
    { displayName: "ROG PG27UCDM", canonicalName: "ASUS ROG Swift OLED PG27UCDM" },
    { displayName: "LG 32GS95UE-B", canonicalName: "LG UltraGear 32GS95UE-B" },
    { displayName: "Alienware AW3225QF", canonicalName: "Dell Alienware AW3225QF" },
  ] },
  { category: "생활 가전", products: [
    { displayName: "로보락 사로스 10R", canonicalName: "Roborock Saros 10R" },
    { displayName: "로보락 큐레보 커브", canonicalName: "Roborock Qrevo Curv" },
    { displayName: "드리미 X50 울트라", canonicalName: "Dreame X50 Ultra" },
    { displayName: "다이슨 젠5 디텍트", canonicalName: "Dyson Gen5detect" },
    { displayName: "다이슨 에어랩 i.d.", canonicalName: "Dyson Airwrap i.d." },
  ] },
  { category: "게이밍", products: [
    { displayName: "닌텐도 스위치 2", canonicalName: "Nintendo Switch 2" },
    { displayName: "플레이스테이션 5 프로", canonicalName: "Sony PlayStation 5 Pro" },
    { displayName: "스팀덱 OLED", canonicalName: "Valve Steam Deck OLED" },
    { displayName: "ROG Xbox Ally X", canonicalName: "ASUS ROG Xbox Ally X" },
    { displayName: "플레이스테이션 포털", canonicalName: "Sony PlayStation Portal" },
  ] },
] as const;

