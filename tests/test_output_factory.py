from talika import RowTable, field


def test_custom_output_builder_receives_record_and_context():
    class UserTable(RowTable):
        name = field("name")

        @classmethod
        def build_output(cls, record, context):
            return {
                "display": f"{context.user_data['prefix']} {record.name}",
                "source_row": record.table_source.row,
            }

    users = UserTable.parse(
        [["name"], ["Alice"]],
        context={"prefix": "Editor"},
    )

    assert users == [{"display": "Editor Alice", "source_row": 2}]
