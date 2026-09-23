from typing import Annotated
from pydantic import BeforeValidator

# Mongo usa ObjectId internamente, pero eso no es serializable a JSON tal cual.
# Este tipo le dice a Pydantic: "conviértelo a string en cuanto lo veas".
PyObjectId = Annotated[str, BeforeValidator(str)]