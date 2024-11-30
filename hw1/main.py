import io

from fastapi import FastAPI, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List

import pandas as pd

import joblib

app = FastAPI()
model = joblib.load('model.pkl')


class Item(BaseModel):
    name: str
    year: int
    selling_price: int
    km_driven: int
    fuel: str
    seller_type: str
    transmission: str
    owner: str
    mileage: str
    engine: str
    max_power: str
    torque: str
    seats: float


class Items(BaseModel):
    objects: List[Item]


def convert_to_kmpl(value):
    if isinstance(value, str):
        if 'km/kg' in value:
            return float(value.replace(' km/kg', '')) * 0.8
        else:
            return float(value.replace(' kmpl', ''))
    else:
        return value


def remove_empty(value):
    if isinstance(value, float):
        return value

    if not value:
        return None
    else:
        new_val = value.replace(' bhp', '')
        if new_val:
            return float(new_val)
        else:
            return None


def preprocess_data(df_object, model_object):
    result = df_object.copy()

    encoding_map = result.groupby('name')['selling_price'].mean()
    result['encoded_name'] = result['name'].map(encoding_map)

    result = pd.get_dummies(result, columns=['fuel'], prefix=['fuel'])
    result = pd.get_dummies(result, columns=['seller_type'], prefix=['seller_type'])
    result = pd.get_dummies(result, columns=['transmission'], prefix=['transmission'])
    result = pd.get_dummies(result, columns=['owner'], prefix=['owner'])

    for col in model_object.feature_names_in_:
        if col not in result:
            result[col] = False

    result['mileage'] = result['mileage'].apply(convert_to_kmpl)
    result['engine'] = result['engine'].str.replace(' CC', '').astype(float)
    result['max_power'] = result['max_power'].apply(remove_empty)

    return result


@app.post("/predict_item")
def predict_item(item: Item) -> float:
    df = pd.DataFrame(item.model_dump(), index=[0])
    df = preprocess_data(df, model)

    result = model.predict(df[model.feature_names_in_])[-1][-1]

    return result


@app.post("/predict_items")
async def predict_items(file: UploadFile):
    contents = await file.read()
    df = pd.read_csv(io.StringIO(contents.decode("utf-8")))

    processed_df = preprocess_data(df, model)
    result = model.predict(processed_df[model.feature_names_in_])

    df["predict"] = pd.DataFrame(result)[0]

    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    response = StreamingResponse(output, media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=processed_{file.filename}"

    return response
