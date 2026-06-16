"""Website quality checks used to qualify cold-call leads."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from ..models.business import WebsiteAnalysis


class WebsiteChecker:
    """Run lightweight website checks that are safe for an MVP crawler."""

    SOCIAL_DOMAINS = (
        "facebook.com",
        "fb.com",
        "instagram.com",
        "linktr.ee",
        "yelp.com",
    )
    FACEBOOK_DOMAINS = ("facebook.com", "fb.com")
    CONTACT_KEYWORDS = ("contact", "quote", "estimate", "message", "email", "request")

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: int = 12,
        user_agent: str | None = None,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.headers = {
            "User-Agent": user_agent
            or (
                "Mozilla/5.0 (compatible; LeadFinder/1.0; "
                "+https://example.com/leadfinder)"
            )
        }

    def check(self, website_url: str | None) -> WebsiteAnalysis:
        """Inspect a website URL and return structured quality signals."""

        if not website_url or not website_url.strip():
            return WebsiteAnalysis(
                url=website_url,
                has_website=False,
                website_type="missing",
                notes=["No website listed on Google profile"],
            )

        normalized_url = self._normalize_url(website_url)
        parsed = urlparse(normalized_url)

        if self._is_facebook_url(parsed.netloc):
            return WebsiteAnalysis(
                url=website_url,
                has_website=True,
                website_type="facebook-only",
                is_facebook_only=True,
                has_ssl=parsed.scheme == "https",
                final_url=normalized_url,
                notes=["Google profile points to Facebook instead of a standalone website"],
            )

        if self._is_social_url(parsed.netloc):
            return WebsiteAnalysis(
                url=website_url,
                has_website=True,
                website_type="social-only",
                has_ssl=parsed.scheme == "https",
                final_url=normalized_url,
                notes=["Google profile points to a social/profile page instead of a website"],
            )

        analysis = WebsiteAnalysis(url=website_url, has_website=True)
        response, errors = self._fetch_first_working_url(normalized_url)
        analysis.notes.extend(errors)

        if response is None:
            analysis.website_type = "broken"
            analysis.is_broken = True
            analysis.load_error = errors[-1] if errors else "Website did not respond"
            analysis.notes.append("Website appears broken or unreachable")
            return analysis

        analysis.status_code = response.status_code
        analysis.final_url = response.url
        analysis.has_ssl = urlparse(response.url).scheme == "https"

        if response.status_code >= 400:
            analysis.website_type = "broken"
            analysis.is_broken = True
            analysis.load_error = f"HTTP {response.status_code}"
            analysis.notes.append(f"Website returned HTTP {response.status_code}")
            return analysis

        if not analysis.has_ssl:
            analysis.website_type = "missing-ssl"
            analysis.notes.append("Website does not appear to support HTTPS")
        else:
            analysis.website_type = "business-website"

        self._analyze_html(response=response, analysis=analysis)
        return analysis

    def _fetch_first_working_url(
        self, normalized_url: str
    ) -> tuple[requests.Response | None, list[str]]:
        """Try HTTPS and HTTP candidates, returning the first non-error response."""

        errors: list[str] = []
        fallback_response: requests.Response | None = None

        for candidate_url in self._candidate_urls(normalized_url):
            try:
                response = self.session.get(
                    candidate_url,
                    headers=self.headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.exceptions.SSLError as exc:
                errors.append(f"SSL error for {candidate_url}: {exc.__class__.__name__}")
                continue
            except requests.RequestException as exc:
                errors.append(f"Request failed for {candidate_url}: {exc.__class__.__name__}")
                continue

            if response.status_code < 400:
                return response, errors

            fallback_response = response

        return fallback_response, errors

    def _analyze_html(self, response: requests.Response, analysis: WebsiteAnalysis) -> None:
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type.lower():
            analysis.notes.append(f"Website returned non-HTML content: {content_type or 'unknown'}")
            return

        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.find("title")
        if title and title.get_text(strip=True):
            analysis.page_title = title.get_text(strip=True)

        analysis.is_mobile_friendly = self._has_viewport_meta(soup)
        if analysis.is_mobile_friendly:
            analysis.notes.append("Mobile friendliness placeholder passed: viewport meta tag found")
        else:
            analysis.notes.append("Mobile friendliness placeholder failed: no viewport meta tag found")

        analysis.has_contact_form = self._has_contact_form(soup)
        if analysis.has_contact_form:
            analysis.notes.append("Contact form heuristic passed")
        elif self._has_contact_link(soup):
            analysis.notes.append("Contact page link found, but no contact form detected on homepage")
        else:
            analysis.notes.append("No contact form detected on homepage")

    def _candidate_urls(self, normalized_url: str) -> list[str]:
        parsed = urlparse(normalized_url)

        if parsed.scheme == "https":
            return [normalized_url, self._replace_scheme(normalized_url, "http")]

        if parsed.scheme == "http":
            return [self._replace_scheme(normalized_url, "https"), normalized_url]

        return [f"https://{normalized_url}", f"http://{normalized_url}"]

    @staticmethod
    def _normalize_url(url: str) -> str:
        clean_url = url.strip()
        if not urlparse(clean_url).scheme:
            clean_url = f"https://{clean_url}"
        return clean_url

    @staticmethod
    def _replace_scheme(url: str, scheme: str) -> str:
        parsed = urlparse(url)
        return urlunparse(parsed._replace(scheme=scheme))

    @classmethod
    def _is_facebook_url(cls, netloc: str) -> bool:
        host = netloc.lower().removeprefix("www.")
        return any(host == domain or host.endswith(f".{domain}") for domain in cls.FACEBOOK_DOMAINS)

    @classmethod
    def _is_social_url(cls, netloc: str) -> bool:
        host = netloc.lower().removeprefix("www.")
        return any(host == domain or host.endswith(f".{domain}") for domain in cls.SOCIAL_DOMAINS)

    @staticmethod
    def _has_viewport_meta(soup: BeautifulSoup) -> bool:
        return (
            soup.find(
                "meta",
                attrs={"name": lambda value: value and value.lower() == "viewport"},
            )
            is not None
        )

    @classmethod
    def _has_contact_form(cls, soup: BeautifulSoup) -> bool:
        for form in soup.find_all("form"):
            class_names = form.get("class", [])
            class_text = " ".join(class_names) if isinstance(class_names, list) else str(class_names)
            form_text = " ".join(
                [
                    form.get("id", ""),
                    class_text,
                    form.get("action", ""),
                    form.get_text(" ", strip=True),
                ]
            ).lower()

            input_names = " ".join(
                input_tag.get("name", "") for input_tag in form.find_all(["input", "textarea"])
            ).lower()

            has_contact_keyword = any(
                keyword in form_text or keyword in input_names for keyword in cls.CONTACT_KEYWORDS
            )
            has_contact_fields = (
                form.find("textarea") is not None
                or form.find("input", attrs={"type": "email"}) is not None
                or form.find("input", attrs={"type": "tel"}) is not None
            )

            if has_contact_keyword or has_contact_fields:
                return True

        return False

    @classmethod
    def _has_contact_link(cls, soup: BeautifulSoup) -> bool:
        for anchor in soup.find_all("a", href=True):
            combined = f"{anchor.get('href', '')} {anchor.get_text(' ', strip=True)}".lower()
            if any(keyword in combined for keyword in cls.CONTACT_KEYWORDS):
                return True
        return False
