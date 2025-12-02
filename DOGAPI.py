import os
import requests
import json
from urllib.parse import urlparse
import time
from tqdm import tqdm


def _get_image_url(url):

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["status"] == "success":
            return data["message"]
        else:
            raise Exception(f"API вернул статус 'error': {data.get('message')}")
    except requests.RequestException as e:
        raise Exception(f"Ошибка при запросе изображения: {e}")


class DogAPI:

    BASE_URL = "https://dog.ceo/api"

    def get_all_breeds(self):

        try:
            response = requests.get(f"{self.BASE_URL}/breeds/list/all", timeout=10)
            response.raise_for_status()
            return response.json()["message"]
        except requests.RequestException as e:
            print(f"🔴 Ошибка при запросе к API dog.ceo: {e}")
            return {}

    def get_breed_image(self, breed):

        url = f"{self.BASE_URL}/breed/{breed}/images/random"
        return _get_image_url(url)

    def get_sub_breed_image(self, breed, sub_breed):

        url = f"{self.BASE_URL}/breed/{breed}/{sub_breed}/images/random"
        return _get_image_url(url)


class YandexDiskUploader:

    UPLOAD_URL = "https://cloud-api.yandex.net/v1/disk/resources/upload"
    CREATE_FOLDER_URL = "https://cloud-api.yandex.net/v1/disk/resources"

    def __init__(self, token):
        self.token = token
        self.headers = {"Authorization": f"OAuth {token}"}

    def create_folder(self, path):

        params = {"path": path}
        try:
            response = requests.put(self.CREATE_FOLDER_URL, headers=self.headers, params=params, timeout=10)
            return response.status_code in (201, 409)  # 201 — создана, 409 — уже существует
        except Exception:
            return False

    def upload_from_url(self, image_url, yandex_path):

        params = {
            "path": yandex_path,
            "url": image_url,
            "overwrite": "true"
        }
        try:
            response = requests.post(self.UPLOAD_URL, headers=self.headers, params=params, timeout=30)
            if response.status_code == 202:
                return True
            elif response.status_code == 409:

                folder_path = os.path.dirname(yandex_path)
                if self.create_folder(folder_path):
                    response = requests.post(self.UPLOAD_URL, headers=self.headers, params=params, timeout=30)
                    return response.status_code == 202
            return False
        except Exception:
            return False


class ImageFilenameHelper:

    @staticmethod
    def get_filename_from_url(url):
        """Извлечь имя файла из URL"""
        filename = os.path.basename(urlparse(url).path)
        if not filename or "." not in filename:
            filename = "image.jpg"
        return filename


class ResultSaver:

    @staticmethod
    def save(results, filename="results.json"):

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"❌ Ошибка при сохранении результатов: {e}")


class DogImageUploader:

    def __init__(self):
        self.dog_api = DogAPI()
        self.filename_helper = ImageFilenameHelper()
        self.result_saver = ResultSaver()
        self.results = []

    def run(self):

        # Ввод данных
        breed = input("🐶 Введите название породы собаки: ").strip().lower()
        yd_token = input("🔑 Введите токен Яндекс.Диска: ").strip()

        if not yd_token:
            print("❗ Токен не может быть пустым.")
            return


        breeds = self.dog_api.get_all_breeds()
        if not breeds:
            print("🔴 Не удалось получить список пород.")
            return

        if breed not in breeds:
            print(f"❌ Порода '{breed}' не найдена.")
            return


        sub_breeds = breeds[breed]
        total_files = 1 + len(sub_breeds) if sub_breeds else 1
        yandex_folder = f"/{breed}/"


        uploader = YandexDiskUploader(yd_token)


        if not uploader.create_folder(yandex_folder):
            print("❌ Не удалось создать папку на Яндекс.Диске.")
            return


        with tqdm(total=total_files, desc="📤 Загрузка", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}]") as pbar:
            self.results.clear()


            self._process_breed_image(breed, yandex_folder, uploader, pbar)


            if sub_breeds:
                for sub_breed in sub_breeds:
                    self._process_sub_breed_image(breed, sub_breed, yandex_folder, uploader, pbar)


        self.result_saver.save(self.results)
        print("🔥 Готово!")

    def _process_breed_image(self, breed, folder_path, uploader, pbar):

        try:
            image_url = self.dog_api.get_breed_image(breed)
            filename = self.filename_helper.get_filename_from_url(image_url)
            yandex_path = folder_path + f"{breed}_{filename}"

            success = uploader.upload_from_url(image_url, yandex_path)
            self.results.append({
                "breed": breed,
                "sub_breed": None,
                "image_url": image_url,
                "yandex_disk_path": yandex_path,
                "status": "uploaded" if success else "failed"
            })
        except Exception:
            self.results.append({
                "breed": breed,
                "sub_breed": None,
                "image_url": None,
                "yandex_disk_path": folder_path + f"{breed}_image.jpg",
                "status": "failed"
            })
        finally:
            pbar.update(1)
            time.sleep(0.5)

    def _process_sub_breed_image(self, breed, sub_breed, folder_path, uploader, pbar):

        try:
            image_url = self.dog_api.get_sub_breed_image(breed, sub_breed)
            filename = self.filename_helper.get_filename_from_url(image_url)
            yandex_path = folder_path + f"{breed}_{sub_breed}_{filename}"

            success = uploader.upload_from_url(image_url, yandex_path)
            self.results.append({
                "breed": breed,
                "sub_breed": sub_breed,
                "image_url": image_url,
                "yandex_disk_path": yandex_path,
                "status": "uploaded" if success else "failed"
            })
        except Exception:
            self.results.append({
                "breed": breed,
                "sub_breed": sub_breed,
                "image_url": None,
                "yandex_disk_path": folder_path + f"{breed}_{sub_breed}_image.jpg",
                "status": "failed"
            })
        finally:
            pbar.update(1)
            time.sleep(0.5)


def main():
    uploader = DogImageUploader()
    uploader.run()


if __name__ == "__main__":
    main()