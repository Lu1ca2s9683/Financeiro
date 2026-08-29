class TestRouter:
    """Keep the simulated Sales DB limited to Django auth infrastructure."""

    sales_db_apps = {"auth", "contenttypes"}

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "vendas":
            return app_label in self.sales_db_apps
        return None
