from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    SESSION_STRING: str = ''

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 63351

    MAX_CLICK_COUNT: int = 160
    MIN_CLICKS_COUNT: int = 5
    MIN_AVAILABLE_COINS: int = 200

    AUTO_BUY_ENERGY_BOOST: bool = False
    MAX_ENERGY_BOOST: int = 10
    AUTO_BUY_SPEED_BOOST: bool = False
    MAX_SPEED_BOOST: int = 10
    AUTO_BUY_CLICK_BOOST: bool = False
    MAX_CLICK_BOOST: int = 10

    ACTIVATE_DAILY_ENERGY: bool = True
    ACTIVATE_DAILY_TURBO: bool = True

    SLEEP_BY_MIN_COINS: bool = True

    USE_PROXY_FROM_FILE: bool = False

    SLEEP_BETWEEN_CLICK: list[int] = [10, 25]
    SLEEP_BEFORE_BUY_MERGE: list[int] = [5, 15]
    SLEEP_BEFORE_ACTIVATE_FREE_BUFFS: list[int] = [5, 15]
    SLEEP_BEFORE_ACTIVATE_TURBO: list[int] = [5, 15]

    SLEEP_AFTER_FORBIDDEN_STATUS: int = 35

    SLEEP_TO_UPDATE_USER_DATA: int = 60 * 5
    SLEEP_BY_MIN_COINS_TIME: int = 60 * 5


settings = Settings()
