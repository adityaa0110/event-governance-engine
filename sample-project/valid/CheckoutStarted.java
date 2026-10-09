void startCheckout() {
    trackEvent("checkout_started", Map.of(
        "cart_id", "cart-1",
        "product_id", "fiber-100",
        "total_amount", 499
    ));
}
