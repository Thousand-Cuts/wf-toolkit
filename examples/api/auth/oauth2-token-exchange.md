# Auth: OAuth2 Token Exchange (Authorization Code Flow)

**What this shows:** POST to `/integrations/oauth2/api/v1/token` to exchange an authorization code for a session token, then use the returned `sessionID` in subsequent API calls.

## Step 1 — Exchange the authorization code for a token

```
POST https://<domain>.my.workfront.com/integrations/oauth2/api/v1/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=<authorization_code_from_callback>
&client_id=<your_oauth2_app_client_id>
&client_secret=<your_oauth2_app_client_secret>
&redirect_uri=<your_registered_redirect_uri>
```

**Response:**
```json
{
  "token_type": "sessionID",
  "expires_in": 7200,
  "access_token": "abc123...sessiontoken...",
  "refresh_token": "def456...refreshtoken..."
}
```

The `access_token` value is the `sessionID`. Use it as a header on every subsequent call.

## Step 2 — Call the API with the sessionID

```
GET https://<domain>.my.workfront.com/attask/api/v17.0/project/search?status=CUR&fields=name,status,plannedCompletionDate
sessionID: abc123...sessiontoken...
```

## Step 3 — Refresh the token before it expires

```
POST https://<domain>.my.workfront.com/integrations/oauth2/api/v1/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&refresh_token=def456...refreshtoken...
&client_id=<your_oauth2_app_client_id>
&client_secret=<your_oauth2_app_client_secret>
```

## Notes

- The OAuth2 app must be configured in **Setup → System → OAuth2 Applications** with "Authorization Code" flow enabled.
- `session_type=sessionID` is the Workfront-native token type. Use `sessionID:` as the header name (not `Authorization: Bearer`).
- For server-to-server jobs with no user context, use `grant_type=client_credentials` instead (see `02-authentication.md`).
- Tokens expire after 2 hours by default. Store the `refresh_token` to get a new access token without re-prompting the user.
