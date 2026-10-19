from Backend import MapParser

if __name__ == "__main__":
    name: str = input("File_name -> ")
    object: MapParser = MapParser(file_name=name)
    #object.test()