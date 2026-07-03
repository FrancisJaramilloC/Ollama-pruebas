class SyntacticService:

    def __init__(self, tokens: list) -> None:
        self.tokens = tokens

    def validate(self) -> dict:
        rules = [
            {
                "token": "INSTRUCCION_INCORPORAR",
                "expected_next": "CANTIDAD_TAZAS",
                "description": (
                    "una instruccion de incorporar debe ir seguida "
                    "de una cantidad en tazas"
                )
            },
            {
                "token": "INSTRUCCION_MEZCLAR",
                "expected_next": "NUMERO",
                "description": (
                    "una instruccion de mezclar debe ir seguida "
                    "de un numero (tiempo en minutos)"
                )
            }
        ]

        for i, token in enumerate(self.tokens):
            ttype = token["type"]
            tvalue = token["value"]

            for rule in rules:
                if ttype != rule["token"]:
                    continue

                if i + 1 >= len(self.tokens):
                    return {
                        "valid": False,
                        "error": (
                            f"Error sintactico en posicion {i}: "
                            f"el token '{ttype}('{tvalue}')' "
                            f"requiere que el siguiente token sea "
                            f"'{rule['expected_next']}', "
                            f"pero no hay mas tokens en la secuencia."
                        )
                    }

                next_token = self.tokens[i + 1]
                next_type = next_token["type"]
                next_value = next_token["value"]

                if next_type != rule["expected_next"]:
                    return {
                        "valid": False,
                        "error": (
                            f"Error sintactico en posicion {i}: "
                            f"el token '{ttype}('{tvalue}')' "
                            f"requiere que el siguiente token sea "
                            f"'{rule['expected_next']}', "
                            f"pero se encontro "
                            f"'{next_type}('{next_value}')'."
                        )
                    }

        return {"valid": True, "error": None}
