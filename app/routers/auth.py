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
            AuthParameters={"USERNAME": payload.username, "PASSWORD": payload.password},
            ClientId=settings.COGNITO_CLIENT_ID,
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in (        if code in (    , "UserNotF        ition        if code in (        if code in (us_c        if code in (        if code in (             if code ition(status_co        if code in (        if code re        if code in (        if code in (    , pons        if code in (        if code in (    , "UserNotF        ition     lt[        if code in (      d_tok        if code en        if code er.        if code in (        del=T        if code in ( ef refresh(payload: RefreshRequest) -> TokenResponse:
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
        access_token=resul        access_token=resul ef        access_token=resul        a       id_token=result["IdToken"],
    )

@router.post("/logout")
async def logout(payload: RefreshRequest):
    try:
        cognito.revoke_token(Token=payload.refresh_token, ClientId=settings.COGNITO_CLIENT_ID)
    except ClientError:
        pass
    return {"message": "logged out"}
