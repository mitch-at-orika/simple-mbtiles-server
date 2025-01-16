{-# LANGUAGE DataKinds #-}
{-# LANGUAGE DeriveGeneric #-}
{-# LANGUAGE FlexibleInstances #-}
{-# LANGUAGE StandaloneDeriving #-}
{-# LANGUAGE TypeOperators #-}

module Types.Config where

import qualified Data.Text as Text
import qualified Options.Generic as OptionsGeneric

data CommandLine w = CommandLine
  { mbtilesFile :: w OptionsGeneric.::: Maybe FilePath OptionsGeneric.<?> "Mbtiles file to serve",
    browser :: w OptionsGeneric.::: Bool OptionsGeneric.<?> "Start a browser with a simple map to view tiles",
    port :: w OptionsGeneric.::: Int OptionsGeneric.<?> "Port to start server"
  }
  deriving (OptionsGeneric.Generic)

modifiers :: OptionsGeneric.Modifiers
modifiers =
  OptionsGeneric.defaultModifiers
    { OptionsGeneric.shortNameModifier = OptionsGeneric.firstLetter
    }

instance OptionsGeneric.ParseRecord (CommandLine OptionsGeneric.Wrapped) where
  parseRecord = OptionsGeneric.parseRecordWithModifiers modifiers

deriving instance Show (CommandLine OptionsGeneric.Unwrapped)

type ContentEncoding = Text.Text