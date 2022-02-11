# -*- coding: UTF-8 -*-

import os
import sys
import pathlib
import urllib
import urllib.parse
from kodi_six import xbmc, xbmcvfs, xbmcaddon
from http_client import HttpClient

__addon__      = xbmcaddon.Addon()
__scriptname__ = __addon__.getAddonInfo('name')

def log(module, msg, level=xbmc.LOGDEBUG):
    """
    输出kodi的log

    参数：
        module          模块名
        msg             信息
        level           log等级
    """
    xbmc.log("{0}::{1} - {2}".format(__scriptname__,module,msg) ,level=level )

def unpack(file_path):
    #支持的字幕后缀
    exts = ( ".srt", ".sub", ".smi", ".ssa", ".ass", ".sup" )
    #支持的压缩包格式
    supported_archive_exts = ( ".zip", ".7z", ".tar", ".tar.gz", ".tar.bz2", ".tar.xz", ".rar" )
    #目标格式
    target_ext = ".zip"

    #判断压缩包格式是否支持
    if not file_path.endswith(supported_archive_exts):
        log(sys._getframe().f_code.co_name, "Unknown file ext: %s" % (os.path.basename(file_path)), level=xbmc.LOGERROR)
        return '', []
    _path = pathlib.Path(file_path)
    #如果压缩包不是目标格式，则转换
    if not file_path.endswith(target_ext):
        http_client = HttpClient()
        #这里通过在线转换
        headers, data = http_client.post("http://vps.familyshen.top:8080/convert", datas = {"file":(_path.name, open(file_path, 'rb').read(), "application/octet-stream"),"to":target_ext}, data_type = "form-data")
        file_path = file_path + target_ext
        with open(file_path, "wb") as f:
            f.write(data)
        xbmc.sleep(500)

    archive_file = urllib.parse.quote_plus(xbmcvfs.translatePath(file_path))
    ext = target_ext[1:]
    #转真实文件路径转换成uri路径
    archive_path = '%(protocol)s://%(archive_file)s' % {'protocol':ext, 'archive_file': archive_file}
    log(sys._getframe().f_code.co_name, "Get %s archive: %s" % (ext, archive_path), level=xbmc.LOGDEBUG)
    #获取压缩包内文件
    dirs, files = xbmcvfs.listdir(archive_path)
    #删除MAC OS的私货
    if ('__MACOSX') in dirs:
        dirs.remove('__MACOSX')
    #通常字幕文件，要么直接将字幕文件打包，要么就是创建一个文件夹将字幕文件打包
    #所以这里不做递归，如果碰到那种混合的，多文件夹的，需要改成递归获取
    #判断如果存在文件夹，则获取文件夹内的文件
    if len(dirs) > 0:
        archive_path = os.path.join(archive_path, dirs[0], '').replace('\\','/')
        dirs, files = xbmcvfs.listdir(archive_path)

    subtitle_list = []
    for subfile in files:
        #判断文件后缀是否是字幕
        if subfile.endswith(exts):
            subtitle_list.append(subfile)

    return archive_path, subtitle_list
