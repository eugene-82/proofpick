const exactDisplayNames: Readonly<Record<string, string>> = {
  "Apple AirPods Pro (3rd generation)": "Apple AirPods Pro 3",
};

export function displayProductName(productName: string): string {
  return exactDisplayNames[productName] ?? productName;
}
