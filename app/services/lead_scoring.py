"""Lead scoring rules for the MVP."""

from __future__ import annotations

from ..models.business import Business, WebsiteAnalysis


class LeadScorer:
    """Convert website checks into cold-call priority scores."""

    def score(self, business: Business) -> Business:
        """Mutate and return a business with score fields populated."""

        analysis = business.website_analysis or WebsiteAnalysis(url=business.website_url)
        score = self._quality_score(analysis)

        business.website_quality_score = score
        business.priority_score = self._priority(score=score, analysis=analysis)
        business.notes.extend(self._score_notes(analysis=analysis, score=score))
        return business

    def _quality_score(self, analysis: WebsiteAnalysis) -> int:
        if not analysis.has_website:
            return 1

        if analysis.is_facebook_only:
            return 20

        if analysis.website_type == "social-only":
            return 25

        if analysis.is_broken:
            return 35

        score = 100

        if not analysis.has_ssl:
            score -= 20

        if analysis.is_mobile_friendly is False:
            score -= 15

        if not analysis.has_contact_form:
            score -= 10

        if analysis.status_code and analysis.status_code >= 300:
            score -= 5

        return max(1, min(100, score))

    def _priority(self, score: int, analysis: WebsiteAnalysis) -> str:
        if not analysis.has_website or analysis.is_facebook_only:
            return "High"

        if analysis.is_broken or score <= 45:
            return "High"

        if score <= 75:
            return "Medium"

        return "Low"

    def _score_notes(self, analysis: WebsiteAnalysis, score: int) -> list[str]:
        notes: list[str] = []

        if not analysis.has_website:
            notes.append("Highest priority: no website found")
        elif analysis.is_facebook_only:
            notes.append("High priority: Facebook-only web presence")
        elif analysis.is_broken:
            notes.append("High priority: website appears broken")
        elif score <= 75:
            notes.append("Medium priority: website has visible improvement opportunities")
        else:
            notes.append("Low priority: website appears functional")

        return notes
