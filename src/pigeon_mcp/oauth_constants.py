# gmail.modify covers settings.sendAs get/list (signatures, identities) and
# settings.filters list/get. filters create/delete need gmail.settings.basic —
# that is the only reason it is requested. Tokens consented under a subset keep
# working for everything but filters_create / filters_delete.
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.modify "
    "https://www.googleapis.com/auth/gmail.send "
    "https://www.googleapis.com/auth/gmail.settings.basic"
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"

STATUS_ACTIVE = "active"
STATUS_NEEDS_AUTH = "needs_auth"
