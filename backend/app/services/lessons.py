"""Micro-lessons: each expert correction becomes a free, personal lesson for the citizen.

Pure function: no DB, no FastAPI. The router persists what this returns via Repo.
"""

from app.services.scoring import final_score


def build_lessons(observation: dict, answers: list[dict], corrections: dict[str, int], note: str) -> list[dict]:
    answers_by_id = {a["indicator_id"]: a for a in answers}
    lessons = []
    for indicator_id, expert_score in corrections.items():
        ans = answers_by_id.get(indicator_id)
        if not ans:
            continue
        your_score = final_score(ans)
        if expert_score == your_score:
            continue
        lessons.append(
            {
                "user_id": observation["user_id"],
                "observation_id": observation["id"],
                "indicator_id": indicator_id,
                "your_score": your_score,
                "expert_score": expert_score,
                "why": note,
            }
        )
    return lessons
