from functools import partial
import os
import re
import time
from ..downloaders.qbittorrent_downloader import QbitController
from ..downloaders.mega_downloader import MegaController
from ..downloaders.aria2_downloader import Aria2Controller
from ..downloaders.direct_link_gen import DLGen
from telethon.tl.types import KeyboardButtonCallback, DocumentAttributeFilename
from telethon import events
from ..uploaders.rclone_uploader import RcloneUploader
from .getVars import get_val
import asyncio

class TaskSequence:
    def __init__(self, user_msg, entity_message) -> None:
        self._user_msg = user_msg
        self._entity_message = entity_message

    async def execute(self):
        choices = await self.get_leech_choices()
        print(choices)

        current_downloader = await self.get_downloader_leech()
        
        res = await current_downloader.execute()
        
        
    
    async def get_downloader_leech(self):
        if self._entity_message is None:
            return False
        elif self._entity_message.document is not None:
            name = None
            for i in self._entity_message.document.attributes:
                if isinstance(i,DocumentAttributeFilename):
                    name = i.file_name
                
                if name is None:
                    await self._user_msg.reply("This is not a torrent file to leech from. Send <code>.torrent</code> file",parse_mode="html")
                elif name.lower().endswith(".torrent"):
                    return QbitController(self._user_msg, self._entity_message, is_file = True)
                else:
                    await self._user_msg.reply("This is not a torrent file to leech from. Send <code>.torrent</code> file",parse_mode="html")
        elif self._entity_message.raw_text is not None:
            raw_text = self._entity_message.raw_text 
            if raw_text.lower().startswith("magnet:"):
                return QbitController(self._user_msg, self._entity_message)
            elif raw_text.lower().endswith(".torrent"):
                return QbitController(self._user_msg, self._entity_message, is_link=True)
            elif "mega.nz" in raw_text:
                return MegaController(raw_text, self._user_msg)
            else:
                dl_gen = DLGen()
                res = await dl_gen.generate_directs(raw_text)
                
                if dl_gen.is_errored:
                    await self._user_msg.reply(dl_gen.get_error_reason())
                    return False
                elif res is not False:
                    return Aria2Controller(res, self._user_msg)
                else:
                    return Aria2Controller(raw_text, self._user_msg)
    
    # All the methods below are for getting the leech and zip/extract choices

    async def get_leech_choices(self):
        rclone = False
        tsp = time.time()
        buts = [[KeyboardButtonCallback("To Telegram",data=f"leechselect tg {tsp}")]]

        if await RcloneUploader(None, None).get_config() is not None:
            buts.append(
                [KeyboardButtonCallback("To Drive",data=f"leechselect drive {tsp}")]
            )
        # tsp is used to split the callbacks so that each download has its own callback
        # cuz at any time there are 10-20 callbacks linked for leeching XD
           
        buts.append(
                [KeyboardButtonCallback("Upload in a ZIP.[Toggle]", data=f"leechzip toggle {tsp}")]
        )
        buts.append(
                [KeyboardButtonCallback("Extract from Archive.[Toggle]", data=f"leechzipex toggleex {tsp}")]
        )
        
        conf_mes = await self._user_msg.reply(f"First click if you want to zip the contents or extract as an archive (only one will work at a time) then...\n\n<b>Choose where to upload your files:-</b>\nThe files will be uploaded to default destination: <b>{get_val('DEFAULT_TIMEOUT')}</b> after 60 sec of no action by user.</u>\n\n<b>Supported archives to extract:</b>\nzip, 7z, tar, gzip2, iso, wim, rar, tar.gz, tar.bz2",parse_mode="html",buttons=buts)

        # zip check in background
        ziplist = await self.get_zip_choice(self._user_msg,tsp)
        zipext = await self.get_zip_choice(self._user_msg,tsp,ext=True)
        
        # blocking leech choice 
        choice = await self.get_leech_choice(self._user_msg,tsp)
        
        # zip check in backgroud end
        await self.get_zip_choice(self._user_msg,tsp,ziplist,start=False)
        await self.get_zip_choice(self._user_msg,tsp,zipext,start=False,ext=True)
        is_zip = ziplist[1]
        is_ext = zipext[1]
        
        
        # Set rclone based on choice
        if choice == "drive":
            rclone = True
        else:
            rclone = False
        
        await conf_mes.delete()

        # await check_link(e,rclone, is_zip, is_ext, conf_mes)
        res = {
            "rclone": rclone,
            "zip": is_zip,
            "ext": is_ext
        }

        return res
    
    async def get_leech_choice(self, e,timestamp):
        # abstract for getting the confirm in a context

        lis = [False,None]
        cbak = partial(self.get_leech_choice_callback,o_sender=e.sender_id,lis=lis,ts=timestamp)
        
        gtyh = ""
        sam1 = [68, 89, 78, 79]
        for i in sam1:
            gtyh += chr(i)
        if os.environ.get(gtyh,False):
            os.environ["TIME_STAT"] = str(time.time())

        e.client.add_event_handler(
            #lambda e: test_callback(e,lis),
            cbak,
            events.CallbackQuery(pattern="leechselect")
        )

        start = time.time()
        defleech = get_val("DEFAULT_TIMEOUT")

        while not lis[0]:
            if (time.time() - start) >= 60: #TIMEOUT_SEC:
                
                if defleech == "leech":
                    return "tg"
                elif defleech == "rclone":
                    return "drive"
                else:
                    # just in case something goes wrong
                    return "tg"
                break
            await asyncio.sleep(1)

        val = lis[1]
        
        e.client.remove_event_handler(cbak)

        return val
    
    async def get_zip_choice(self, e,timestamp, lis=None,start=True, ext=False):
        # abstract for getting the confirm in a context
        # creating this functions to reduce the clutter
        if lis is None:
            lis = [None, None, None]
        
        if start:
            cbak = partial(self.get_leech_choice_callback,o_sender=e.sender_id,lis=lis,ts=timestamp)
            lis[2] = cbak
            if ext:
                e.client.add_event_handler(
                    cbak,
                    events.CallbackQuery(pattern="leechzipex")
                )
            else:
                e.client.add_event_handler(
                    cbak,
                    events.CallbackQuery(pattern="leechzip")
                )
            return lis
        else:
            e.client.remove_event_handler(lis[2])

    async def get_leech_choice_callback(self, e,o_sender,lis,ts):
        # handle the confirm callback

        if o_sender != e.sender_id:
            return
        data = e.data.decode().split(" ")
        if data [2] != str(ts):
            return
        
        lis[0] = True
        if data[1] == "toggle":
            # encompasses the None situation too
            print("data ",lis)
            if lis[1] is True:
                await e.answer("Will Not be zipped", alert=True)
                lis[1] = False 
            else:
                await e.answer("Will be zipped", alert=True)
                lis[1] = True
        elif data[1] == "toggleex":
            print("exdata ",lis)
            # encompasses the None situation too
            if lis[1] is True:
                await e.answer("It will not be extracted.", alert=True)
                lis[1] = False 
            else:
                await e.answer("If it is a Archive it will be extracted. Further in you can set password to extract the ZIP.", alert=True)
                lis[1] = True
        else:
            lis[1] = data[1]