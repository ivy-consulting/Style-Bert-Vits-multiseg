def split_text_by_punctuation_and_newlines(text):
    import re

    def is_english(text):
        # Basic check: majority of characters are ASCII (a-zA-Z)
        english_chars = sum(c.isascii() and c.isalpha() for c in text)
        return english_chars / max(len(text), 1) > 0.5

    sentences = []

    if is_english(text):
        # English logic
        words = text.split()

        # First 3 words
        sentences.append(' '.join(words[:3]))

        # Next 5 words
        sentences.append(' '.join(words[3:8]))

        # Remaining text after removing the first 8 words
        remaining_text = ' '.join(words[8:])

        # Split remaining using punctuation (Japanese + English + newline)
        punctuation_pattern = r'(?:(?<=\.)(?<!\d\.)|(?<=[!?。！？．]))(?=\s|$)'
        chunks = [chunk.strip() for chunk in re.split(punctuation_pattern, remaining_text) if chunk.strip()]
        sentences.extend(chunks)


    else:
        # Japanese or non-English logic: skip word slicing
        punctuation_pattern = r'(?<=[。！？!?\n])\s*'
        chunks = [chunk.strip() for chunk in re.split(punctuation_pattern, text) if chunk.strip()]
        sentences.extend(chunks)

    return sentences


# === Test with Japanese ===
jp_text = "今日はとてもいい天気です。朝から太陽が出ていて、空は青く、雲がほとんどありません。私は公園へ散歩に行きました。鳥の声を聞きながら、のんびりと歩くのはとても気持ちがよかったです。"
print("Japanese:")
print(split_text_by_punctuation_and_newlines(jp_text))

# === Test with English ===
en_text = "Today is a beautiful day・ The sun is shining, the sky is blue, and the air is fresh. I went for a walk in the park. It was very peaceful and relaxing. we got 3.3 million dollars. yay, i like her and she got 2.2/10 isnt it creazy?"
print("\nEnglish:")
print(split_text_by_punctuation_and_newlines(en_text))
