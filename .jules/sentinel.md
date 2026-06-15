## 2024-06-15 - [Sentinel] Fix Open Redirect in Login Flow
**Vulnerability:** Open Redirect vulnerability in the login endpoint where the `next` parameter could be exploited by using backslash-based URLs like `\\attacker.com`.
**Learning:** `urlparse(url).netloc` evaluates `\\attacker.com` to an empty `netloc`, making the previous check `if not next_page or urlparse(next_page).netloc != ''` ineffective against this bypass, yet modern browsers will still interpret `\\attacker.com` as a valid absolute URL and redirect to it.
**Prevention:** Avoid relying solely on `urlparse` to prevent open redirects. Instead, implement an explicit `is_safe_url` helper function that strictly enforces that the URL starts with a single `/` and reject URLs starting with `//` or `\\`.
