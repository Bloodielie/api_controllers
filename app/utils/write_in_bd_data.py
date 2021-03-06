import re
from asyncio import sleep
from typing import Iterator

from orm import Model

from app.configuration.config import UPDATE_TIME
from app.configuration.config_variables import id_groups
from app.utils.getting_stops_data import get_max_value_bd
from app.utils.getting_vk_posts import VkPostGetter, VkPostGetterAbstract
from app.utils.validation import validation_bus_stop, PostCleaner, PostCleanerAbstract
from app.utils.vk_api import VkApiAbstract


class Writer:
    def __init__(self, vk: VkApiAbstract):
        self.vk = vk
        self._post_getter = VkPostGetter(self.vk)
        self._post_cleaner = PostCleaner()

    async def write_in_database(self, model: Model) -> None:
        data_utils = DataGetter(model.__name__.lower(), self._post_getter, self._post_cleaner)
        while True:
            vk_post: list = await data_utils.get_rewrite_post()
            if not len(vk_post):
                await sleep(UPDATE_TIME)
                continue
            data_post = data_utils.get_cleaning_post(vk_post)
            stop = data_utils.get_bus_stop()
            data: list = validation_bus_stop(data_post, stop)
            datas: list = list(sorted(data, key=lambda x: x[1]))
            await self.write_data_bd(model, datas, 'time')
            await sleep(UPDATE_TIME)

    @staticmethod
    async def write_data_bd(model: Model, data: list, column_name: str) -> None:
        max_time_bd: int = await get_max_value_bd(model, column_name)
        for _data in data:
            if _data[1] > max_time_bd:
                await model.objects.create(bus_stop=_data[0], time=_data[1])

    @property
    def post_getter(self):
        return self._post_getter

    @post_getter.setter
    def post_getter(self, value: VkPostGetterAbstract):
        if isinstance(value, VkPostGetterAbstract):
            self._post_getter = value
        else:
            raise TypeError('Post_getter should inherit from VkPostGetterAbstract')

    @property
    def post_cleaner(self):
        return self._post_cleaner

    @post_cleaner.setter
    def post_cleaner(self, value: PostCleanerAbstract):
        if isinstance(value, PostCleanerAbstract):
            self._post_getter = value
        else:
            raise TypeError('Post_cleaner should inherit from PostCleanerAbstract')


class DataGetter:
    def __init__(self, name_class: str, vk_post_getter: VkPostGetterAbstract, post_cleaner: PostCleanerAbstract):
        self.name_class = name_class
        self.vk_post_getter = vk_post_getter
        self.post_cleaner = post_cleaner

    async def get_rewrite_post(self):
        id_group: int = self._get_id_group(self.name_class)
        if self.name_class.find('gomel') != -1:
            return await self.vk_post_getter.comment_data_getter(id_group)
        else:
            return await self.vk_post_getter.post_data_getter(id_group)

    def get_bus_stop(self) -> list:
        for key_city in id_groups.keys():
            city_name = re.search(key_city, self.name_class)
            if not city_name:
                continue
            else:
                return id_groups.get(city_name[0])[1]

    @staticmethod
    def _get_id_group(name_class: str) -> int:
        for key_city in id_groups.keys():
            city_name = re.search(key_city, name_class)
            if not city_name:
                continue
            else:
                return id_groups.get(city_name[0])[0]

    def get_cleaning_post(self, vk_post: list) -> Iterator[tuple]:
        if self.name_class.find('dirty') != -1:
            return self.post_cleaner.cleaning_posts(vk_post, 'dirty')
        else:
            return self.post_cleaner.cleaning_posts(vk_post, 'clean')
