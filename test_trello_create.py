from integrations.trello import create_card

card = create_card(
    name="[TEST] MeetFlow Integration",
    description="Test card created by MeetFlow. Safe to delete after verification."
)

print("TEST CARD CREATED!")
print("Card:", card["name"])
print("URL:", card["url"])