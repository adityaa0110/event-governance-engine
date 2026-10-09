func buyNow() {
    trackEvent("purchase_button_clicked", properties: [
        "product_id": "fiber-100",
        "product_category": "broadband",
        "price": 499,
        "customer_type": "existing"
    ])
}
