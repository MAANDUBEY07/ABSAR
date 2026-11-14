from pydantic import BaseModel, ConfigDict


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
