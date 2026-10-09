// Correct standardized tracking — Event Governance should PASS this.

export function onBuyNowClick(product) {
  trackEvent("purchase_button_clicked", {
    product_id: "123",
    product_category: "broadband",
    price: 499,
    customer_type: "existing",
  });
}

function trackEvent(name, props) {
  console.log("track", name, props);
}