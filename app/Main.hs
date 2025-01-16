{-# LANGUAGE OverloadedStrings #-}

module Main where

import qualified Lib
import qualified Options.Generic as OptionsGeneric
import qualified Types.Config as Config
import qualified System.Exit as SystemExit

main :: IO ()
main = do
  commandLineOpts <- OptionsGeneric.unwrapRecord "simple-mbtiles-server"
  doIt commandLineOpts

doIt :: Config.CommandLine OptionsGeneric.Unwrapped -> IO ()
doIt (Config.CommandLine mbtilesfile startBrowser port) = do
  case mbtilesfile of
    Just mbtf ->
      Lib.startApp mbtf startBrowser port

    Nothing -> do
      putStrLn $ "No mbtiles file specified"
      SystemExit.exitWith (SystemExit.ExitFailure 2)
