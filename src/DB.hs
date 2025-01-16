module DB where

import qualified Control.Monad.Trans as MonadTrans (liftIO)
import qualified Data.ByteString as BS
import qualified Data.ByteString.Lazy.Char8 as ByteStringLazyChar8
import qualified Data.Char as Char
import qualified Data.HashMap.Strict as HashMap
import qualified Data.Maybe as Maybe
import qualified Data.Text as Text
import qualified Data.Text.Encoding as TextEncoding
import qualified Data.Text.Read as TextRead
import qualified Database.Mbtiles as Mbtiles
import qualified Errors
import qualified Servant
import qualified Types.Config as Config

metadataDB ::
  Mbtiles.MbtilesPool ->
  Servant.Handler (HashMap.HashMap Text.Text Text.Text)
metadataDB conns =
  Mbtiles.runMbtilesPoolT conns Mbtiles.getMetadata

getTileEncoding :: Mbtiles.MbtilesPool -> IO Config.ContentEncoding
getTileEncoding conns = do
  metadata <- Mbtiles.runMbtilesPoolT conns Mbtiles.getMetadata
  pure $
    if pCOptionSet metadata
      then "identity"
      else "gzip"

pCOptionSet :: HashMap.HashMap Text.Text Text.Text -> Bool
pCOptionSet metadata =
  Maybe.maybe False lastGeneratorPc (HashMap.lookup "generator_options" metadata)

lastGeneratorPc :: Text.Text -> Bool
lastGeneratorPc genOpts =
  case a of
    x : _ ->
      last a
    _ ->
      False
  where
    a = map (Text.isInfixOf "-pC") (Text.splitOn ";" genOpts)

tilesDB ::
  Config.ContentEncoding ->
  Mbtiles.MbtilesPool ->
  Int ->
  Int ->
  Text.Text ->
  Servant.Handler (Servant.Headers '[Servant.Header "Content-Encoding" Text.Text] BS.ByteString)
tilesDB contentEncoding conns z x stringY
  | (".mvt" `Text.isSuffixOf` stringY) || (".pbf" `Text.isSuffixOf` stringY) || (".vector.pbf" `Text.isSuffixOf` stringY) =
    Servant.addHeader contentEncoding <$> (getAnything conns z x stringY)
  | otherwise = Servant.throwError $ Servant.err400 {Servant.errBody = "Unknown request: " <> ByteStringLazyChar8.fromStrict (TextEncoding.encodeUtf8 stringY)}

getAnything ::
  Mbtiles.MbtilesPool ->
  Int ->
  Int ->
  Text.Text ->
  Servant.Handler BS.ByteString
getAnything conns z x stringY =
  case getY stringY of
    Left e -> Servant.throwError $ Servant.err400 {Servant.errBody = "Unknown request: " <> ByteStringLazyChar8.fromStrict (TextEncoding.encodeUtf8 stringY)}
    Right (y, _) -> getTile conns z x y
  where
    getY s = TextRead.decimal $ Text.takeWhile Char.isNumber s

getTile :: Mbtiles.MbtilesPool -> Int -> Int -> Int -> Servant.Handler BS.ByteString
getTile conns z x y = do
  res <- MonadTrans.liftIO $ action
  case res of
    Just a ->
      return a
    Nothing -> do
      Servant.throwError Servant.err404 {Servant.errBody = Errors.errorString "404" "No tiles found" "Try requesting a different tile."}
  where
    action =
      Mbtiles.runMbtilesPoolT conns (Mbtiles.getTile (Mbtiles.Tile (Mbtiles.Z z, Mbtiles.X x, Mbtiles.Y y)))
