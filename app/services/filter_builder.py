class KufarFilterBuilder:
    def __init__(self, filters: dict):
        self.filters = filters if filters else {}
        self.params = {}

    def _set_single_value(self, key, values):
        if values and isinstance(values, list):
            self.params[key] = values[0]

    def _set_multi_value(self, key, values, logic="or"):
        if values and isinstance(values, list):
            self.params[key] = f"v.{logic}:{','.join(map(str, values))}"

    def build(self) -> dict:
        self._set_multi_value("crg", self.filters.get("crg"))
        self._set_multi_value("cre", self.filters.get("cre"))
        self._set_multi_value("crt", self.filters.get("crt"))
        self._set_single_value("rgn", self.filters.get("rgn"))
        self._set_single_value("crd", self.filters.get("crd"))
        self._set_single_value("cnd", self.filters.get("cnd"))
        return self.params
