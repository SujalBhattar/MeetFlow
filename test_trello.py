
from integrations.trello import (
    test_connection,
    verify_board,
    verify_todo_list
)

print("\nMEETFLOW - TRELLO CONNECTION TEST")
print("=" * 45)

try:
    member = test_connection()
    print("\nCONNECTED SUCCESSFULLY!")
    print("Account:", member["fullName"])

    board = verify_board()
    print("\nBOARD VERIFIED!")
    print("Board:", board["name"])

    todo_list = verify_todo_list()
    print("\nLIST VERIFIED!")
    print("List:", todo_list["name"])

    print("\n" + "=" * 45)
    print("ALL CONNECTION TESTS PASSED!")

except Exception as error:
    print("\nCONNECTION FAILED")
    print("Error:", error)
