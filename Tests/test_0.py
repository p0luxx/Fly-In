def hub_processor(value: str) -> None:
    name, x, y = value.split(" ", 2)
    extras = {}
    if value.index("[") and value.index("]"):
        start, end = value.index("[") + 1, value.index("]")
        print(f"Start -> {start} ----- End -> {end}")
        extra_content = value[start:end]
        print(f"Extra content -> {extra_content}")
        print(f"Split -> ", extra_content.split(" "))
    #print(f"{name}\n{x}\n{y}\n{extras}")



if __name__ == "__main__":
    s: str = input("-> ")
    print(hub_processor(s))