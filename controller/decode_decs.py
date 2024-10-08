from loguru import logger
import re
import redis

class DecodDeCS:
    def __init__(self, redis_host='iahx_controller_cache', redis_port=6379, redis_db=0):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)
        self.REGEX = re.compile(r"(\^[ds])(\d+)")  # Pre-compile regex pattern

    def close(self):
        if self.redis_client:
            self.redis_client.close()

    def decode(self, text, lang):
        """
        Decode a given string by replacing ^d or ^s codes with their corresponding descriptors from Redis.
        """
        buffer = []
        matcher = self.REGEX.finditer(text)

        # Collect all descriptor codes from the text
        codes = {match.group(2).lstrip('0') for match in matcher}

        # Fetch all descriptor terms in bulk from Redis
        descriptors = self.bulk_fetch_descriptors(codes, lang)

        # Reset matcher after collecting codes
        matcher = self.REGEX.finditer(text)

        last_end = 0
        for match in matcher:
            subcampo = match.group(1)  # Either ^d or ^s
            codigo = match.group(2).lstrip('0')  # The numerical code, stripped of leading zeros
            descritor = descriptors.get(codigo)

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

    def bulk_fetch_descriptors(self, codes, lang):
        """
        Fetch descriptor terms in bulk from Redis using the provided list of codes and language.
        """
        pipeline = self.redis_client.pipeline()
        for code in codes:
            pipeline.hgetall(f"decs:{code}")
        results = pipeline.execute()

        descriptors = {}
        for code, result in zip(codes, results):
            if result:
                if lang == 'es':
                    descriptors[code] = result.get(b'es')
                elif lang == 'pt':
                    descriptors[code] = result.get(b'pt-br')
                elif lang == 'fr':
                    descriptors[code] = result.get(b'fr')
                else:
                    descriptors[code] = result.get(b'en')

        # Decode the bytes to string if a descriptor is found
        return {k: v.decode('utf-8') if v else None for k, v in descriptors.items()}


# Example usage:
if __name__ == "__main__":
    decod = DecodDeCS(redis_host='iahx_controller_cache', redis_port=6379, redis_db=0)
    result = decod.decode("Loren ^d22016  loren lipson ^d1327 loren ^d12009^s22016", 'pt')
    print(result)
