import os
import re

class GalleryTime:
    def __init__(self, base_path):
        print("Program Start\n")
        self.base_path = base_path
        self.images = []
        self.images_by_date = {} 
        self.load_images()
        self.store_images_by_date()

    def get_year(self, file):
        return int(file[:4])

    def get_month(self, file):
        return int(file[5:7])

    def is_valid(self, file):
        return file[0:2] == "20" and file[-1] != "4"

    def load_images(self):
        print("Loading Images\n")
        for _, _, files in  os.walk(self.base_path):
            for file in files:
                if self.is_valid(file): 
                    self.images.append(file)
        self.images.sort()
    
    def store_images_by_date(self):
        print("Storing Images")
        for image in self.images:
            year = self.get_year(image)
            if year not in self.images_by_date:
                self.images_by_date[year] = {}
            month = self.get_month(image)
            if month not in self.images_by_date[year]:
                self.images_by_date[year][month] = []
            self.images_by_date[year][month].append(image)


if __name__ == "__main__":
    photo_directory = "/home/filipe/Pictures/Fotos"
    viewer = GalleryTime(photo_directory)

