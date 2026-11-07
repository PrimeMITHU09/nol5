import random
import string
import uuid
import requests

BASE_URL = "https://mail.cx/v1"
DEFAULT_DOMAINS = ["uqu.me", "ddker.com", "9k3r.com"]

class MailCX:
    def __init__(self, api_token=None):
        self.api_token = api_token
        self.client_id = str(uuid.uuid4())

    def _get_headers(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "X-Client-ID": self.client_id,
            "Accept": "application/json"
        }
        if self.api_token:
            headers["x-api-token"] = self.api_token
        return headers

    def get_domains(self):
        try:
            r = requests.get(f"{BASE_URL}/config", headers=self._get_headers(), timeout=5)
            if r.status_code == 200:
                data = r.json()
                domains = [d["domain"] for d in data.get("system_domains", []) if "domain" in d]
                if domains:
                    return domains
        except Exception:
            pass
        return DEFAULT_DOMAINS

    def generate_email(self, domain=None):
        if not domain:
            domain = DEFAULT_DOMAINS[0]
        # 6-8 random lowercase alphanumeric chars
        rand_len = random.randint(6, 8)
        prefix = "".join(random.choices(string.ascii_lowercase + string.digits, k=rand_len))
        return f"{prefix}@{domain}"

    def check_inbox(self, address: str, timeout: int = 5):
        """
        Polls inbox. If timeout is short, and server holds connection for up to 25s,
        a requests.Timeout indicates no mail arrived yet (returns empty list).
        """
        try:
            r = requests.get(
                f"{BASE_URL}/inbox/{address}",
                headers=self._get_headers(),
                timeout=timeout
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict):
                    return data.get("emails", [])
                elif isinstance(data, list):
                    return data
                return []
            elif r.status_code == 204:
                return []
            else:
                return []
        except requests.exceptions.Timeout:
            return []
        except Exception as e:
            print(f"Inbox error: {e}")
            return []

    def get_email_detail(self, email_id: str):
        try:
            r = requests.get(
                f"{BASE_URL}/email/{email_id}",
                headers=self._get_headers(),
                timeout=8
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"Email detail error: {e}")
        return None

    def delete_inbox(self, address: str):
        try:
            r = requests.delete(
                f"{BASE_URL}/inbox/{address}",
                headers=self._get_headers(),
                timeout=5
            )
            return r.status_code in [200, 204]
        except Exception:
            return False

