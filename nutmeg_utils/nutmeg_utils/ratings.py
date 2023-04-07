from typing import Dict, List


class MatchStats:
    def __init__(self,
                 id,
                 going: List[str],
                 raw_scores: Dict[str, Dict[str, float]],
                 skills_scores: Dict[str, Dict[str, List[str]]]):
        self.id = id
        self.going = going
        self.raw_scores = raw_scores
        self.raw_skill_scores = skills_scores

    def get_user_scores(self) -> Dict[str, float]:
        user_scores = {}
        for u in self.raw_scores:
            positive_scores = [v for v in self.raw_scores[u].values() if v > 0]
            if len(positive_scores) > 1:
                user_scores[u] = sum(positive_scores) / len(positive_scores)
        return user_scores

    def get_user_skills(self) -> Dict[str, Dict[str, int]]:
        user_skill_scores = {}

        for u in self.raw_skill_scores:
            if len(self.raw_scores[u]) > 1:
                for _, skills in self.raw_skill_scores[u].items():
                    for s in skills:
                        if u not in user_skill_scores:
                            user_skill_scores[u] = {}
                        user_skill_scores[u][s] = user_skill_scores[u].get(s, 0) + 1

        return user_skill_scores

    def get_potms(self) -> (List[str], float):
        if len(self.get_user_scores()) == 0:
            return None
        sorted_user_scores = sorted(self.get_user_scores().items(), reverse=True, key=lambda x: x[1])
        potm_score = sorted_user_scores[0][1]
        potms = [x[0] for x in sorted_user_scores if x[1] == potm_score]
        return potms, potm_score

    def __repr__(self):
        return "{}\n{}\n{}".format(str(self.going), str(self.raw_scores), str(self.raw_skill_scores))
