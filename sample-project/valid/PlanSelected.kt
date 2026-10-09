fun selectPlan() {
    trackEvent(
        "plan_selected",
        mapOf(
            "plan_id" to "fiber-100",
            "plan_name" to "Fiber 100",
            "price" to 499
        )
    )
}
