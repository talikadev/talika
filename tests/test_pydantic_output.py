import pydantic
import pytest

from talika import RowTable, TableError, field


class UserModel(pydantic.BaseModel):
    name: str
    age: int = pydantic.Field(ge=18)


def test_pydantic_model_uses_the_standard_output_contract():
    class UserTable(RowTable):
        name: str = field("name", required=True)
        age: int = field("age", required=True)

    users = UserTable.parse_as(
        [["name", "age"], ["Alice", "30"]],
        UserModel,
    )

    assert users == [UserModel(name="Alice", age=30)]


def test_pydantic_validation_errors_keep_record_location():
    class UserTable(RowTable):
        output_model = UserModel

        name: str = field("name", required=True)
        age: int = field("age", required=True)

    with pytest.raises(TableError, match="greater than or equal to 18") as error:
        UserTable.parse_as([["name", "age"], ["Alice", "16"]])

    assert error.value.row == 2
