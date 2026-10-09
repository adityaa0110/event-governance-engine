// Intentionally broken tracking — Event Governance should FAIL this.

export function onBuyNowClick(product) {
  trackEvent("buy_now", {
    productId: 123,
    price: "499",
  });
}

function trackEvent(name, props) {
  console.log("track", name, props);
}