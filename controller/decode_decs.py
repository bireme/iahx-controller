from loguru import logger

import re
import redis

class DecodDeCS:
    def __init__(self, redis_host='iahx_controller_cache', redis_port=6379, redis_db=0):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)

    def decode(self, text, lang):
        """
        Decode a given string by replacing ^d or ^s codes with their corresponding descriptors from memory database.
        """
        descritor = ""

        REGEX = re.compile(r"(\^[ds])(\d+)")
        buffer = []
        matcher = REGEX.finditer(text)

        last_end = 0
        for match in matcher:
            subcampo = match.group(1)  # Either ^d or ^s
            codigo = match.group(2)  # The numerical code following ^d or ^s
            descritor = None

            try:
                 # Fetch the descriptor term from memory database based on the code and language
                descritor = self.get_descriptor_term(codigo, lang)
            except Exception as ex:
                logger.error(f"Error retrieving descriptor for code {codigo}: {ex}")

             # If no descriptor is found, fall back to the original code
            if not descritor:
                descritor = f"{subcampo}{codigo}"
            else:
                # Add / before the term for qualifiers
                if subcampo == "^s":
                    descritor = f"/{descritor}"

            # Append the substring before the match and the found/replaced descriptor
            buffer.append(text[last_end:match.start()])
            buffer.append(descritor)
            last_end = match.end()

        buffer.append(text[last_end:])

        return "".join(buffer)

    def get_descriptor_term(self, code, lang):
        """
        Fetch the descriptor term from memory database using the provided code and language.
        """
        descriptor = None

        code = code.lstrip('0')

        logger.info(f"Fetching descriptor for code {code} in language {lang}")
        descriptor_term = self.redis_client.hgetall(f"decs:{code}")

        if descriptor_term:
             # Get the descriptor based on the requested language
            if lang == 'es':
                descriptor = descriptor_term.get(b'es')
            elif lang == 'pt':
                descriptor = descriptor_term.get(b'pt-br')
            elif lang == 'fr':
                descriptor = descriptor_term.get(b'fr')
            else:
                descriptor = descriptor_term.get(b'en')

        # Decode the bytes to string if a descriptor is found
        descriptor_str = descriptor.decode('utf-8') if descriptor else None

        return descriptor_str


# Example usage:
if __name__ == "__main__":
    decod = DecodDeCS(redis_host='iahx_controller_cache', redis_port=6379, redis_db=0)
    result = decod.decode("Olá ^d22016  tudo bem ^d1327 some text ^d12009^s22016", 'pt')
    print(result)
