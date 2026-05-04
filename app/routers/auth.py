import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
cognito = boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    id_token: str
    token_type: str = "Bearer"


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    try:
        resp = cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": payload.username,
                "PASSWORD": payload.password,
            },
            ClientId=settings.COGNITO_CLIENT_ID,
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("NotAuthorizedException", "UserNotFoundException"):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        raise HTTPException(status_code=400, detail=str(e))

    result = resp["AuthenticationResult"]
    return TokenResponse(
        access_token=result["AccessToken"],
        refresh_token=result["RefreshToken"],
        id_token=result["IdToken"],
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest) -> TokenResponse:
    try:
        resp = cognito.initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={"REFRESH_TOKEN": payload.refresh_token},
            ClientId=settings.COGNITO_CLIENT_ID,
        )
    except ClientError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    result = resp["AuthenticationResult"]
    return TokenResponse(
        access_token=result["AccessToken"],
        refresh_token=payload.refresh_token,
        id_token=result["IdToken"],
    )


@router.post("/logout")
async def logout(payload: RefreshRequest):
    try:
        cognito.revoke_token(
            Token=payload.refresh_token,
            ClientId=settings.COGNITO_CLIENT_ID,
        )
    except ClientError:
        pass
    return {"message": "logged out"}
