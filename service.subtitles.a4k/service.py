# -*- coding: utf-8 -*-

import os
import sys
import time
import re
import urllib
import urllib.parse
import requests
from bs4 import BeautifulSoup
from kodi_six import xbmc, xbmcgui, xbmcaddon, xbmcplugin, xbmcvfs


__addon__      = xbmcaddon.Addon()
__author__     = __addon__.getAddonInfo("author")
__scriptid__   = __addon__.getAddonInfo("id")
__scriptname__ = __addon__.getAddonInfo("name")
__version__    = __addon__.getAddonInfo("version")
__language__   = __addon__.getLocalizedString

__cwd__        = xbmcvfs.translatePath( __addon__.getAddonInfo("path") )
__profile__    = xbmcvfs.translatePath( __addon__.getAddonInfo("profile") )
__resource__   = xbmcvfs.translatePath( os.path.join( __cwd__, "resources", "lib" ) )
__temp__       = xbmcvfs.translatePath( os.path.join( __profile__, "temp") )

sys.path.append (__resource__)

import archive
from http_client import HttpClient

A4K_API = "https://www.a4k.net"

def log(module, msg, level=xbmc.LOGDEBUG):
    """
    输出kodi的log

    参数：
        module          模块名
        msg             信息
        level           log等级
    """
    xbmc.log("{0}::{1} - {2}".format(__scriptname__,module,msg) ,level=level )

def search(search_str):
    """
    根据关键词检索字幕

    参数：
        search_str      检索关键词
    """
    log(sys._getframe().f_code.co_name ,"Search str %s" % (search_str))
    http_client = HttpClient()
    try:
        #检索页面
        headers, data = http_client.get(A4K_API + "/search", params = {"term": search_str})
        soup = BeautifulSoup(data, "html.parser")
    except Exception as e:
        log( sys._getframe().f_code.co_name ,"%s: %s    Error searching." % (Exception, e), level=xbmc.LOGERROR)
        return
    #用BeautifulSoup解析返回的页面
    results = soup.find_all("li", class_ = "item")
    for it in results:
        content_ele = it.select("div[class=\"content\"]")
        if content_ele is None or len(content_ele) != 1:
            break
        content_ele = content_ele[0].h3.a
        #获取字幕文件名
        file_name = content_ele.string
        #获取字幕的详情页URL
        url = urllib.parse.urljoin(A4K_API, content_ele.get("href"))
        #获取该字幕所有的语言
        langs = []
        for lit in it.select("div[class=\"language\"]")[0].select("i"):
            langs.append(lit.get("data-content"))
        log( sys._getframe().f_code.co_name ,"file_name = %s, url = %s, langs = %s" % (file_name, url, str(langs)), level=xbmc.LOGDEBUG)
        if "简体" in langs or "繁体" in langs or "双语" in langs:
            language_name = "Chinese"
            language_flag = "zh"
        elif "英文" in langs:
            language_name = "English"
            language_flag = "en"
        else:
            language_name = "Unknown"
            language_flag = "en"
        #将字幕文件添加到kodi的列表中
        listitem = xbmcgui.ListItem(label = language_name, label2 = file_name)
        listitem.setArt({"icon": "0", "thumb": language_flag})
        plugin_url = "plugin://%s/?action=download&link=%s" % (__scriptid__, urllib.parse.quote_plus(url))
        xbmcplugin.addDirectoryItem(handle = int(sys.argv[1]), url = plugin_url, listitem = listitem, isFolder = False)

def store_file(filename, data):
    """
    将文件保存到temp文件夹下

    参数：
        filename        文件名
        data            数据

    返回值：
        文件的绝对路径
    """
    tempfile = os.path.join(__temp__, filename)
    with open(tempfile, "wb") as f:
        f.write(data)
    return tempfile.replace("\\","/")

def download(url):
    """
    下载字幕文件

    参数：
        url             下载链接

    返回值：
        字幕列表
    """
    http_client = HttpClient()
    #如果临时文件夹不存在则创建
    if not xbmcvfs.exists(__temp__.replace("\\","/")):
        xbmcvfs.mkdirs(__temp__)
    #删除旧的文件
    dirs, files = xbmcvfs.listdir(__temp__)
    for f in files:
        xbmcvfs.delete(os.path.join(__temp__, f))
    subtitle_list = []
    #支持的字幕后缀
    exts = (".srt", ".sub", ".smi", ".ssa", ".ass", ".sup" )
    #支持的压缩包格式
    supported_archive_exts = ( ".zip", ".7z", ".tar", "rar", ".tar.gz", ".tar.bz2", ".tar.xz" )

    log(sys._getframe().f_code.co_name ,"Download page: %s" % (url))
    try:
        #获取字幕的详情页
        headers, data = http_client.get(url)
        soup = BeautifulSoup(data, "html.parser")
        #获取字幕文件的下载链接
        download_url = soup.find("a", class_ = "ui green button").get("href")

        #如果不是http和https开头的，则把前缀拼上去
        if not (download_url.startswith("http://") or download_url.startswith("https://")):
            download_url = urllib.parse.urljoin(A4K_API, download_url)
        log(sys._getframe().f_code.co_name ,"Download links: %s" % (download_url))
        #获取字幕的文件名
        filename = urllib.parse.unquote_plus(download_url.split("/")[-1])
        log(sys._getframe().f_code.co_name ,"filename: %s" % (filename))
        #如果文件后缀是字幕文件，则直接使用
        if filename.endswith(exts):
            headers, data = http_client.get(download_url)
            tempfile = store_file(filename, data)
            subtitle_list.append(tempfile)
        #如果文件是压缩包
        elif filename.endswith(supported_archive_exts):
            #下载压缩包文件
            headers, data = http_client.get(download_url)
            #保存到本地
            tempfile = store_file(filename, data)
            xbmc.sleep(500)
            #解压，获取文件列表
            archive_path, flist = archive.unpack(tempfile)
            #如果只有一个字幕文件，则直接使用
            if len(flist) == 1:
                subtitle_list.append( os.path.join( archive_path, flist[0] ).replace("\\","/"))
            #如果大于1个，则让用户选择
            elif len(flist) > 1:
                sel = xbmcgui.Dialog().select("select subtitle", flist)
                if sel == -1:
                    sel = 0
                subtitle_list.append(os.path.join(archive_path, flist[sel]).replace("\\","/"))
        else:
            log(sys._getframe().f_code.co_name, "Unsupported file: %s" % (filename), level=xbmc.LOGWARNING)
            xbmc.executebuiltin(("XBMC.Notification(\"a4k\",\"不支持的压缩格式，请选择其他字幕文件。\")"), True)


    except:
        log(sys._getframe().f_code.co_name, "Error (%d) [%s]" % (
            sys.exc_info()[2].tb_lineno,
            sys.exc_info()[1]
            ),
            level=xbmc.LOGERROR
            )
        return []

    if len(subtitle_list) > 0:
        log(sys._getframe().f_code.co_name, "Get subtitle file: %s" % (subtitle_list[0]), level=xbmc.LOGINFO)
    return subtitle_list

def title_friendly(title):
    """
    处理标题，去除一些无用的信息

    参数：
        title               标题

    返回值：
        更友好的标题
    """
    #将[xxx]都去除
    s = re.sub("\[[^[]]+\]", "", title)
    #根据[. \t]去分割标题
    sarr = re.split("[. \t]+", s)
    ft = ""
    year = ""
    for s in sarr:
        if len(re.findall("^\d+$", s)) == 1:
            #用于判断是否是年份，年份通常大于1900小于5000（5000年以后此插件也将不复存在）
            if int(s) > 1900 and int(s) < 5000:
                year = s
        #根据一般字幕文件规律，都是到720p、1080p为止，后面都是无用信息
        elif len(re.findall("^\d+[pP]$", s)) == 1:
            break
        else:
            #将有用的信息用空格重组
            if year != "":
                ft = ft + year + " "
                year = ""
            ft = ft + s + " "
    #去除最后一个空格
    if len(ft) > 1:
        return ft[0:-1]
    else:
        return ft

def get_params():
    """
    获取参数

    返回值：
        参数的map
    """
    param_map = {}
    paramstring = sys.argv[2]
    if paramstring[0] == "?":
        paramstring = paramstring[1:]
    paramstring = paramstring.split("/")[0]
    if len(paramstring) == 0:
        return param_map
    for param in paramstring.split("&"):
        sparam = param.split("=")
        param_map[sparam[0]] = urllib.parse.unquote_plus(sparam[1])
    return param_map

#获取参数
param_map = get_params()
#如果action为search或者manualsearch则搜索
if param_map["action"] == "search" or param_map["action"] == "manualsearch":
    #获取TV show的标题
    tvshow_title = urllib.parse.unquote_plus(xbmc.getInfoLabel("VideoPlayer.TVshowtitle"))
    #获取一般标题
    title = urllib.parse.unquote_plus(xbmc.getInfoLabel("VideoPlayer.Title"))

    search_str = ""
    #如果searchstring存在，则是手动搜索的，优先采用手动搜索的关键词
    if "searchstring" in param_map:
        search_str = param_map["searchstring"]
    #判断TV show的标题是否存在，存在则采用
    elif len(tvshow_title) > 0:
        log(sys._getframe().f_code.co_name, "tvshow title = " + tvshow_title)
        search_str = title_friendly(tvshow_title)
    #否则使用一般标题
    else:
        log(sys._getframe().f_code.co_name, "title = " + title)
        search_str = title_friendly(title)
    log(sys._getframe().f_code.co_name, " search_str = " + search_str)
    #调用搜索方法
    search(search_str)

#如果action为download则下载字幕
elif param_map["action"] == "download":
    #调用下载方法
    subs = download(param_map["link"])
    #将字幕文件添加到kodi的列表中
    for sub in subs:
        listitem = xbmcgui.ListItem(label=sub)
        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=sub,listitem=listitem,isFolder=False)

xbmcplugin.endOfDirectory(int(sys.argv[1]))
