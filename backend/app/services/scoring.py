"""Pure scoring helpers. No DB, no FastAPI, so services and routers can share them."""


def final_score(ans: dict) -> int | None:
    if ans.get("used_ai_answer") and ans.get("ai_score") is not None:
        return ans["ai_score"]
    return ans.get("human_score")
