module Lib
  ( startApp,
  )
where

import qualified Controller
import qualified DB (getTileEncoding)
import qualified Data.Text as Text
import qualified Database.Mbtiles as Mbtiles
import qualified Network.Wai as Wai
import qualified Network.Wai.Handler.Warp as Wai (run)
import qualified Routes
import qualified Servant
import qualified System.Exit as SystemExit
import qualified Web.Browser as Browser

debug :: Wai.Middleware
debug app req resp = do
  putStrLn "Request headers:"
  print (Wai.requestHeaders req)
  app req resp

getTilesPool :: FilePath -> IO (Either Mbtiles.MBTilesError Mbtiles.MbtilesPool)
getTilesPool file = do
  Mbtiles.getMbtilesPool file

startApp :: FilePath -> Bool -> Int -> IO ()
startApp mbtilesfile startBrowser port = do
  mbTilesConnsOrError <- getTilesPool mbtilesfile
  case mbTilesConnsOrError of
    Left e -> do
      putStrLn $ show e
      SystemExit.exitWith (SystemExit.ExitFailure 2)
    Right spatialConns -> do
      contentEncoding <- DB.getTileEncoding spatialConns
      let action = Wai.run port $ debug $ Servant.serve Routes.api (Controller.server contentEncoding spatialConns)
      if startBrowser
        then do
          b <- Browser.openBrowser $ Text.unpack "http://127.0.0.1" ++ ":" ++ show port
          if b
            then action
            else print "Failed to start browser"
        else action
