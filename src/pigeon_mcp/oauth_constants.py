# gmail.modify also covers settings.sendAs get/list (signatures, identities), so no
# settings scope is requested. Tokens consented under the older three-scope set keep
# working — Google's refresh honours the superset.
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.modify "
    "https://www.googleapis.com/auth/gmail.send"
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"

STATUS_ACTIVE = "active"
STATUS_NEEDS_AUTH = "needs_auth"
