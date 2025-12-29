from jose import jwt, JWTError
import requests
from typing import Optional, Dict
import os
from datetime import datetime, timedelta

class MicrosoftAuthService:
    """Service for validating Microsoft ID tokens"""
    
    def __init__(self):
        self.client_id = os.getenv("MICROSOFT_CLIENT_ID")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID", "common")
        self.authority = os.getenv("MICROSOFT_AUTHORITY", f"https://login.microsoftonline.com/{self.tenant_id}")
        self.issuer = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"
        self._keys_cache = None
        self._keys_cache_time = None
        
    def get_signing_keys(self) -> Dict:
        """Fetch Microsoft's public signing keys (with 24-hour caching)"""
        # Cache keys for 24 hours to reduce API calls
        if self._keys_cache and self._keys_cache_time:
            if datetime.now() - self._keys_cache_time < timedelta(hours=24):
                return self._keys_cache
        
        keys_url = f"{self.authority}/discovery/v2.0/keys"
        response = requests.get(keys_url, timeout=10)
        response.raise_for_status()
        self._keys_cache = response.json()
        self._keys_cache_time = datetime.now()
        return self._keys_cache
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify Microsoft ID token and return claims.
        
        Args:
            token: JWT ID token from Microsoft
            
        Returns:
            Dict of claims if valid, None if invalid
        """
        try:
            # Get signing keys from Microsoft
            jwks = self.get_signing_keys()
            
            # Decode header to get key ID
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                print("Missing 'kid' in token header")
                return None
            
            # Find the matching public key
            key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
            if not key:
                print(f"Unable to find matching signing key for kid: {kid}")
                return None
            
            # Verify and decode the token
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.client_id,
                options={"verify_aud": True, "verify_exp": True}
            )
            
            # Validate issuer (must be from Microsoft)
            token_issuer = claims.get("iss", "")
            if not token_issuer.startswith("https://login.microsoftonline.com/"):
                print(f"Invalid issuer: {token_issuer}")
                return None
            
            print(f"Token validated successfully for user: {claims.get('email', claims.get('preferred_username'))}")
            return claims
            
        except JWTError as e:
            print(f"JWT validation failed: {str(e)}")
            return None
        except requests.RequestException as e:
            print(f"Failed to fetch signing keys: {str(e)}")
            return None
        except Exception as e:
            print(f"Unexpected error during token validation: {str(e)}")
            return None
